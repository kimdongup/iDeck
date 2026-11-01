#!/usr/bin/env bash
# Build100 / Wine native iOS build recovery.
# Read-only --plan; --configure generates Wine host headers using the
# pinned Wine source; --native cross-compiles the 3 iOS archives.
# Never changes iPhone, signing, bundle ID, or git history.
set -euo pipefail
ROOT="/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck"
WINE="$ROOT/wine"
BUILD="$WINE/build-macos"
LOGDIR="/Volumes/Repository/cokacremote/iDeckRuntimeLab/diagnostics/native-build"
MINGW_DIR="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal"
MINGW_BIN="$MINGW_DIR/bin"
MODE="${1:---plan}"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This needs Xcode on the Mac. Do not run inside cokacremote3 Linux."
  exit 2
fi
case "$MODE" in --plan|--configure|--native|--all) ;; *)
  echo "Usage: $0 [--plan|--configure|--native|--all]" >&2; exit 2 ;; esac
if [[ ! -f "$WINE/configure" || ! -d "$ROOT/app/Madeira.xcodeproj" ]]; then
  echo "Wine source or Xcode project missing: $WINE" >&2; exit 3
fi
if [[ "$(git -C "$WINE" rev-parse HEAD)" != "9129e9684daaeae70da9435e7c6060e59392634e" ]]; then
  echo "Wrong Wine source revision; refusing to mix unrelated Wine ABIs." >&2; exit 3
fi

echo "=== iDeck Build100 Wine native ==="
echo "Mode: $MODE"
echo "Wine source: $(git -C "$WINE" rev-parse --short HEAD)"
echo "Toolchain: $(xcodebuild -version | tr '\n' ' ')"

# Wine 11 on Apple ARM64 *requires* a Windows ARM64 PE cross compiler even
# when only building the native Darwin headers (Wine configure: PE_ARCHS).
# Select the EXACT 2026-04-21 LLVM-MinGW version pinned in docs/BUILDING.md.
# Do not silently mix this fork with arbitrary Homebrew or Xcode clang.
if [[ -x "$MINGW_BIN/aarch64-w64-mingw32-clang" &&
      -x "$MINGW_BIN/llvm-dlltool" && -x "$MINGW_BIN/ld.lld" ]]; then
  export PATH="$MINGW_BIN:$PATH"
  echo "Pinned LLVM-MinGW PE compiler: $MINGW_BIN/aarch64-w64-mingw32-clang"
else
  echo "Pinned LLVM-MinGW PE compiler: MISSING"
  echo "Expected: $MINGW_BIN/aarch64-w64-mingw32-clang"
  echo "The official 20260421 macOS universal archive is required."
fi

# Apple ships GNU Bison 2.3 even with current macOS/Xcode. Wine 11 requires
# GNU Bison >=3.0 and supports a BISON environment override. Homebrew installs
# its newer bison as keg-only: it is often NOT the first bison in PATH.
# Never change or symlink /usr/bin/bison; select a project-local tool path.
find_recent_bison() {
  local candidate version major brew_prefix
  local -a candidates=()
  if [[ -n "${BISON:-}" ]]; then candidates+=("$BISON"); fi
  if command -v bison >/dev/null 2>&1; then
    candidates+=("$(command -v bison)")
  fi
  if command -v brew >/dev/null 2>&1; then
    brew_prefix="$(brew --prefix bison 2>/dev/null || true)"
    if [[ -n "$brew_prefix" ]]; then candidates+=("$brew_prefix/bin/bison"); fi
  fi
  candidates+=(/opt/homebrew/opt/bison/bin/bison /usr/local/opt/bison/bin/bison)
  for candidate in "${candidates[@]}"; do
    [[ -x "$candidate" ]] || continue
    version="$("$candidate" --version 2>/dev/null | head -n 1)"
    version="${version##* }"
    major="${version%%.*}"
    if [[ "$major" =~ ^[0-9]+$ ]] && (( major >= 3 )); then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

BISON_BIN="$(find_recent_bison || true)"
if [[ -n "$BISON_BIN" ]]; then
  export BISON="$BISON_BIN"
  echo "Selected Bison: $BISON ($("$BISON" --version | head -n 1))"
else
  echo "Bison >=3.0: NOT FOUND (macOS system bison 2.3 is insufficient)"
  echo "Install: brew install bison"
fi
for program in xcrun make clang ar python3; do
  if command -v "$program" >/dev/null; then echo "  present: $program";
  else echo "  MISSING: $program"; fi
done
if [[ "$MODE" == "--plan" ]]; then
  echo "1. Configure $BUILD (macOS host headers, no phone changes)."
  echo "2. Compile iOS ntdll and win32u archives."
  echo "3. Compile wineserver archive (requires llvm-objcopy)."
  echo "4. Re-run Build100 preflight."
  if [[ -s "$BUILD/include/config.h" && -f "$BUILD/Makefile" ]]; then
    echo "Configured Wine headers: YES"
  else
    echo "Configured Wine headers: NOT YET"
  fi
  if command -v llvm-objcopy >/dev/null; then
    echo "llvm-objcopy: $(command -v llvm-objcopy)"
  elif [[ -x /opt/homebrew/opt/llvm/bin/llvm-objcopy ]]; then
    echo "llvm-objcopy: /opt/homebrew/opt/llvm/bin/llvm-objcopy"
  else
    echo "llvm-objcopy: MISSING (wineserver build will need Homebrew LLVM)"
  fi
  exit 0
fi

for program in xcrun make clang ar python3; do
  if ! command -v "$program" >/dev/null; then
    echo "Missing build tool: $program" >&2; exit 3
  fi
done
mkdir -p "$LOGDIR"

run_logged() {
  local name="$1"; shift
  local logfile="$LOGDIR/$name.log"
  echo "=== $name ==="
  set +e
  "$@" 2>&1 | tee "$logfile"
  local rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$rc" -ne 0 ]]; then
    echo "BUILD FAILED ($name; exit $rc): $logfile"
    exit "$rc"
  fi
  echo "PASS $name"
}

if [[ "$MODE" == "--configure" || "$MODE" == "--all" ]]; then
  if [[ -s "$BUILD/include/config.h" && -f "$BUILD/Makefile" ]]; then
    echo "Wine build-macos config already exists; reusing without overwriting."
  else
    if [[ -z "$BISON_BIN" ]]; then
      echo "Wine configure requires GNU Bison >= 3.0." >&2
      echo "Install with: brew install bison" >&2
      echo "Then re-run: $0 --configure" >&2
      exit 3
    fi
    if [[ ! -x "$MINGW_BIN/aarch64-w64-mingw32-clang" ||
          ! -x "$MINGW_BIN/llvm-dlltool" || ! -x "$MINGW_BIN/ld.lld" ]]; then
      echo "Wine on ARM64 requires the pinned LLVM-MinGW PE toolchain:" >&2
      echo "$MINGW_BIN" >&2
      echo "Cannot fall back to Apple clang for PE cross-compilation." >&2
      exit 3
    fi
    # Verify both compilation AND PE linking before running a costly Wine
    # configure: Apple clang alone can compile C but cannot link Windows PE.
    probe_dir="$(mktemp -d "${TMPDIR:-/tmp/}ideck-wine-pe.XXXXXXXX")"
    if ! printf 'int main(void) { return 0; }\n' | \
         "$MINGW_BIN/aarch64-w64-mingw32-clang" -x c - \
         -o "$probe_dir/probe.exe"; then
      rm -rf "$probe_dir"
      echo "Pinned llvm-mingw cannot link a Windows ARM64 PE executable on this Mac." >&2
      exit 3
    fi
    rm -rf "$probe_dir"
    echo "PASS pinned LLVM-MinGW ARM64 PE compile/link smoke test"
    mkdir -p "$BUILD"
    (
      cd "$BUILD"
      # Out-of-tree Wine 11 configure for native macOS headers; do not
      # choose an ARM64EC PE cross target for the Darwin unix-side build.
      # $BISON is exported above; this overrides macOS /usr/bin/bison 2.3.
      run_logged wine-configure ../configure --disable-tests --with-mingw=llvm-mingw
    )
    if [[ ! -s "$BUILD/include/config.h" || ! -f "$BUILD/Makefile" ]]; then
      echo "Wine configure did not generate include/config.h and Makefile." >&2
      exit 5
    fi
  fi
fi
if [[ "$MODE" == "--configure" ]]; then
  echo "Configure stage complete; archives have not been built."
  exit 0
fi

if [[ ! -s "$BUILD/include/config.h" || ! -f "$BUILD/Makefile" ]]; then
  echo "Wine build-macos unconfigured. Run: $0 --configure" >&2; exit 5
fi
# Reconstruct source prerequisites before compiling ntdll: the previous
# attempt compiled 35 of 37 objects, failing only on missing headers.
run_logged wine-prerequisites bash /Volumes/Repository/cokacremote/iDeckRuntimeLab/build100-prepare-wine-headers-on-mac.sh --prepare
# Build current port's native iOS archives; not an upstream full Wine build.
run_logged wine-ntdll-ios bash "$ROOT/build/ntdll-unix/build.sh"
# The upstream ntdll script prints a failure count but, on a dirty tree,
# may still package old *.o members. Reject such a misleading success.
if grep -Eq "Results: [0-9]+ succeeded, [1-9][0-9]* failed" "$LOGDIR/wine-ntdll-ios.log"; then
  echo "ntdll had compilation failures despite the build script exit status." >&2
  exit 6
fi
run_logged wine-win32u-ios bash "$ROOT/build/win32u-unix/build.sh"
if ! command -v llvm-objcopy >/dev/null &&
   [[ ! -x /opt/homebrew/opt/llvm/bin/llvm-objcopy ]]; then
  echo "ntdll/win32u built, but wineserver requires llvm-objcopy." >&2
  echo "Install Homebrew llvm or supply llvm-objcopy in PATH, then re-run --native." >&2
  exit 3
fi
run_logged wine-wineserver-ios bash "$ROOT/build/wineserver/build.sh"
for name in libntdll_unix.a libwin32u_unix.a libwineserver.a; do
  if [[ ! -s "$ROOT/app/Madeira/$name" ]]; then
    echo "Expected native archive is missing after build: $name" >&2; exit 6
  fi
  echo "Produced $name ($(stat -f %z "$ROOT/app/Madeira/$name") bytes)"
done
echo "Re-running Build100 dependency check."
python3 /Volumes/Repository/cokacremote/iDeckRuntimeLab/build100-preflight.py \
  --repo "$ROOT" --no-discover \
  --output /Volumes/Repository/cokacremote/iDeckRuntimeLab/diagnostics/mac-build100-preflight.json
