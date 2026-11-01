#!/usr/bin/env bash
# Build101: targeted Wine PE runtime bootstrap files, without rebuilding native Wine.
# Host: Apple Silicon Mac + Xcode + pinned llvm-mingw.
# Targets: Wine ARM64 WoW64 boot subset and i386 ntdll/kernelbase/kernel32/user32.
# This is a BOOT SUBSET; full Steam/CEF import closure remains a separate gate.
set -euo pipefail

WORK="/Volumes/Repository/cokacremote/iDeckRuntimeLab"
R="$WORK/iDeck"
WINE="$R/wine"
B="$WINE/build-bootstrap-pe"
OUT="$WORK/build101-artifacts/pe-build"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
MODE="${1:---plan}"
JOBS="${WINE_PE_JOBS:-1}"
PIN="9129e9684daaeae70da9435e7c6060e59392634e"

case "$MODE" in --plan|--configure|--aarch64-boot|--i386-ntdll|--all) ;; *)
  echo "Usage: $0 [--plan|--configure|--aarch64-boot|--i386-ntdll|--all]" >&2; exit 2;;
esac
[[ "$(uname -s)" == "Darwin" ]] || { echo "Run this script on your Mac." >&2; exit 2; }
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo "WINE_PE_JOBS must be >=1" >&2; exit 2; }
[[ "$(git -C "$WINE" rev-parse HEAD)" == "$PIN" ]] || {
  echo "Pinned Wine revision changed; refusing to build mismatched Wine PE modules." >&2; exit 3;
}
for prog in make xcrun python3; do
  command -v "$prog" >/dev/null || { echo "Missing program: $prog" >&2; exit 3; }
done
for bin in aarch64-w64-mingw32-clang i686-w64-mingw32-clang aarch64-w64-mingw32-strip i686-w64-mingw32-strip; do
  [[ -x "$TC/$bin" ]] || { echo "Missing pinned llvm-mingw tool: $TC/$bin" >&2; exit 3; }
done
export PATH="$TC:$PATH"
if command -v brew >/dev/null 2>&1; then
  BISON_DIR="$(brew --prefix bison 2>/dev/null)/bin" || BISON_DIR=""
  if [[ -n "$BISON_DIR" && -x "$BISON_DIR/bison" ]]; then
    export PATH="$BISON_DIR:$PATH"
  fi
fi
echo "=== Build101 Wine PE bootstrap ($MODE) ==="
echo "Wine SHA: $(git -C "$WINE" rev-parse --short HEAD)"
echo "Wine build: $B"
echo "Bison: $(bison --version 2>/dev/null | head -1 || echo unavailable)"
echo "Compilation jobs: $JOBS"
echo "Current target files:"
for p in aarch64-windows/cmd.exe aarch64-windows/explorer.exe i386-windows/ntdll.dll; do
  [[ -s "$R/app/Madeira/$p" ]] && echo "  PRESENT $p" || echo "  MISSING $p"
done
echo "Note: the ARM64EC DLL farm and Microsoft x64 VC runtime are separate prerequisites."

if [[ "$MODE" == "--plan" ]]; then
  echo "Stages: --configure -> --aarch64-boot -> --i386-ntdll (or --all)."
  echo "This does not build the full Wine PE DLL dependency closure."
  exit 0
fi

mkdir -p "$OUT"
run_logged() {
  local stage="$1"; shift
  echo "=== $stage ==="
  set +e
  "$@" 2>&1 | tee "$OUT/wine-pe-bootstrap-$stage.log"
  local rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$rc" -ne 0 ]]; then
    echo "FAILED: $stage ($rc). See $OUT/wine-pe-bootstrap-$stage.log" >&2
    exit "$rc"
  fi
  echo "PASS: $stage"
}

# Keep a separate build root, so native wine/build-macos and LLVM remain untouched.
# Wine's official --enable-archs accepts both aarch64 and i386 in one build.
if [[ ! -f "$B/config.status" || ! -f "$B/Makefile" ]]; then
  mkdir -p "$B"
  if [[ -f "$B/config.status" || -f "$B/Makefile" ]]; then
    echo "Half-configured Wine bootstrap build detected. Inspect $B first; not deleting it." >&2
    exit 4
  fi
  run_logged configure bash -c 'cd "$1"; shift; exec "$@"' _ "$B" \
    "$WINE/configure" \
    --enable-archs=aarch64,i386 --with-mingw=llvm-mingw \
    --without-x --without-vulkan --without-freetype --without-gnutls \
    --disable-tests --enable-winegstreamer
fi
[[ -f "$B/Makefile" ]] || { echo "Wine bootstrap Makefile missing." >&2; exit 4; }
[[ "$MODE" != "--configure" ]] || { echo "PASS: bootstrap PE configure"; exit 0; }

targets=()
if [[ "$MODE" == "--aarch64-boot" || "$MODE" == "--all" ]]; then
  targets+=(programs/cmd/aarch64-windows/cmd.exe programs/explorer/aarch64-windows/explorer.exe)
fi
if [[ "$MODE" == "--i386-ntdll" || "$MODE" == "--all" ]]; then
  targets+=(dlls/ntdll/i386-windows/ntdll.dll)
fi
if [[ "$MODE" == "--all" ]]; then
  targets+=(
    dlls/ntdll/aarch64-windows/ntdll.dll
    dlls/wow64/aarch64-windows/wow64.dll
    dlls/wow64win/aarch64-windows/wow64win.dll
    dlls/win32u/aarch64-windows/win32u.dll
    dlls/kernelbase/aarch64-windows/kernelbase.dll
    dlls/apisetschema/aarch64-windows/apisetschema.dll
    dlls/kernelbase/i386-windows/kernelbase.dll
    dlls/kernel32/i386-windows/kernel32.dll
    dlls/win32u/i386-windows/win32u.dll
    dlls/user32/i386-windows/user32.dll
    dlls/apisetschema/i386-windows/apisetschema.dll
  )
fi
[[ "${#targets[@]}" -gt 0 ]] || exit 3
avail_kb="$(df -Pk "$B" | awk 'END {print $4}')"
if [[ ! "$avail_kb" =~ ^[0-9]+$ ]] || (( avail_kb < 8 * 1024 * 1024 )); then
  echo "Less than 8GiB free in Wine bootstrap build volume. Not compiling." >&2
  exit 5
fi
run_logged compile make -C "$B" -j"$JOBS" "${targets[@]}"

# Validate the actual PE machine word before staging, not merely filename/size.
validate_pe() {
  local path="$1" machine="$2"
  python3 - "$path" "$machine" <<'PY'
import pathlib, struct, sys
p = pathlib.Path(sys.argv[1])
expected = int(sys.argv[2], 16)
data = p.read_bytes()
if len(data) < 0x100 or data[:2] != b'MZ':
    raise SystemExit(f"Invalid PE (MZ missing): {p}")
offset, = struct.unpack_from("<I", data, 0x3c)
if offset + 6 > len(data) or data[offset:offset + 4] != b'PE\0\0':
    raise SystemExit(f"Invalid PE signature: {p}")
machine, = struct.unpack_from("<H", data, offset + 4)
if machine != expected:
    raise SystemExit(f"PE machine mismatch {p}: 0x{machine:04x} expected 0x{expected:04x}")
print(f"VALIDATED PE 0x{machine:04x}, {len(data)} bytes: {p}")
PY
}

for target in "${targets[@]}"; do
  src="$B/$target"
  [[ -s "$src" ]] || { echo "Missing expected PE output $src" >&2; exit 6; }
  case "$target" in
    */aarch64-windows/*) mach=aa64; strip="$TC/aarch64-w64-mingw32-strip";;
    */i386-windows/*)   mach=014c; strip="$TC/i686-w64-mingw32-strip";;
    *) echo "Unexpected stage arch: $target" >&2; exit 6;;
  esac
  validate_pe "$src" "$mach"
  staging="$OUT/$(basename "$target").$mach.tmp"
  cp -p "$src" "$staging"
  "$strip" --strip-debug "$staging"
  validate_pe "$staging" "$mach"
  dest_arch="$(basename "$(dirname "$target")")"
  dest="$R/app/Madeira/$dest_arch/$(basename "$target")"
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" ]]; then
    validate_pe "$dest" "$mach"
    echo "PRESERVED existing valid PE: $dest"
    rm -f "$staging"
    continue
  fi
  mv -n "$staging" "$dest"
  [[ -s "$dest" ]] || { echo "Failed to install PE file: $dest" >&2; exit 7; }
  echo "STAGED $dest"
done
echo "PASS: requested Wine PE bootstrap files (not a full WoW64 runtime)."
run_logged audit python3 "$WORK/build100-preflight.py" --repo "$R" --no-discover \
    --output "$WORK/diagnostics/mac-build101-preflight.json"
