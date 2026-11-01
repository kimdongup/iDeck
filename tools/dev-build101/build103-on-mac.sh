#!/bin/bash
# Build a NEW, separately identified iDeck Build103 test IPA on macOS.
# Does not install/uninstall anything on the iPhone.
# Default: audit only. Opt in to --build once dependencies are complete.
set -euo pipefail

ROOT="${BUILD103_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
WORK="/Volumes/Repository/cokacremote/iDeckRuntimeLab"
BUNDLE="${BUILD103_BUNDLE_ID:-com.kimdongup.ideck.build100}"
TEAM="${BUILD103_TEAM_ID:-KADCK35KR7}"
# Source repo is already on the APFS external SSD. macOS disk audit on
# 2026-10-31 confirmed 346 GiB free there vs 7.2 GiB on internal Data.
# Store DerivedData, test app, IPA and logs on that same external volume.
# BUILD103_DERIVED_DATA / BUILD103_OUTPUT can override independently.
# Preserve Build100 toolchains/prefix and cached DerivedData for incremental builds.
ARTIFACTS="$WORK/build100-artifacts"
DERIVED="${BUILD103_DERIVED_DATA:-$ARTIFACTS/DerivedData/iDeckBuild100}"
OUT="${BUILD103_OUTPUT:-$WORK/build103-artifacts/Output}"
MODE="${1:---audit}"

if [[ "$MODE" != "--audit" && "$MODE" != "--build" ]]; then
  echo "Usage: $0 [--audit | --build]"
  exit 2
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on the user's Mac with Xcode, not inside Linux."
  exit 2
fi
if [[ ! -d "$ROOT/app/Madeira.xcodeproj" ]]; then
  echo "Missing app project: $ROOT/app/Madeira.xcodeproj"
  exit 2
fi
if [[ ! "$BUNDLE" =~ ^[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z0-9_-]+)+$ ]]; then
  echo "Invalid bundle ID: $BUNDLE"
  exit 2
fi
if [[ "$BUNDLE" == "com.kuschqin.madeira.steamui" || "$BUNDLE" == "com.kuscholar.ideck.steamui" ]]; then
  echo "Refusing to use a publisher-owned or upstream bundle ID on this Personal Team."
  exit 2
fi
if [[ ! "$TEAM" =~ ^[A-Za-z0-9]{10}$ ]]; then
  echo "Expected 10-character Apple Team ID."
  exit 2
fi

mkdir -p "$WORK/diagnostics"
echo "=== Build103 readiness ==="
echo "Bundle: $BUNDLE"
echo "Team: $TEAM"
echo "Action: $MODE"
if [[ "$MODE" == "--audit" ]]; then
  python3 "$ROOT/tools/dev-build101/build100-preflight.py" \
    --repo "$ROOT" --output "$WORK/diagnostics/mac-build103-preflight.json"
  echo "Audit completed without building, registering app IDs, or altering device."
  exit 0
fi
# For --build, validate again after assembling any missing Wine prefix.
# Audit mode remains strictly read-only.

# Xcode itself runs on macOS, but its build and packaged outputs use the
# chosen storage volume. Default is the external APFS Repository volume.
# A mounted external volume is essential: never accidentally write to an
# internal /Volumes/Repository directory if the drive has been unplugged.
if [[ "$DERIVED" == "$ARTIFACTS/"* || "$OUT" == "$ARTIFACTS/"* ]]; then
  if ! mount | grep -F " on /Volumes/Repository (" >/dev/null; then
    echo "External Repository disk is not mounted: /Volumes/Repository" >&2
    echo "Refusing to create build outputs on the internal fallback path." >&2
    exit 3
  fi
fi
mkdir -p "$OUT" "$DERIVED"
echo "=== Build103 destination volumes ==="
echo "DerivedData: $DERIVED"
echo "Build log and IPA: $OUT"
df -h "$DERIVED" "$OUT"
avail_kb="$(df -Pk "$DERIVED" | awk 'END {print $4}')"
if [[ ! "$avail_kb" =~ ^[0-9]+$ ]] || (( avail_kb < 8 * 1024 * 1024 )); then
  echo "Insufficient free disk on build volume (need >=8GiB before build): $DERIVED" >&2
  echo "=== Disk status ===" >&2
  df -h "$DERIVED" "$OUT" >&2
  if [[ "$avail_kb" =~ ^[0-9]+$ ]]; then
    awk -v kb="$avail_kb" 'BEGIN {
      printf "Available on DerivedData volume: %.2f GiB; minimum: 8 GiB; recommended: 15+ GiB.\n", kb/1048576
    }' >&2
  fi
  echo "For read-only storage diagnostics, run:" >&2
  echo "  bash $WORK/build100-disk-audit-on-mac.sh" >&2
  echo "No caches, snapshots, or existing build files were deleted." >&2
  exit 3
fi

# Rebuild native NTDLL so the Build103 wine-bootstrap trace is linked.
# Then build pinned ARM64/i386 Wine PE boot DLLs before packaging.
echo "=== Build103 native Wine / PE bootstrap ==="
# Preserve the previously working Build100 link inputs before replacing them.
mkdir -p "$WORK/build103-artifacts/backup/native-static"
for lib in libntdll_unix.a libwin32u_unix.a libwineserver.a; do
  src="$ROOT/app/Madeira/$lib"
  dest="$WORK/build103-artifacts/backup/native-static/$lib"
  if [[ -s "$src" && ! -e "$dest" ]]; then cp -p "$src" "$dest"; fi
done
bash "$ROOT/tools/dev-build101/build100-wine-native-on-mac.sh" --native
bash "$ROOT/tools/dev-build101/build101-wine-pe-on-mac.sh" --all
for pe in aarch64-windows/ntdll.dll aarch64-windows/wow64.dll           aarch64-windows/wow64win.dll i386-windows/ntdll.dll           i386-windows/kernelbase.dll i386-windows/kernel32.dll           i386-windows/user32.dll; do
  if [[ ! -s "$ROOT/app/Madeira/$pe" ]]; then
    echo "Missing Wine PE runtime before Xcode: $pe" >&2
    exit 4
  fi
done

# Build103: kernel32 ARM64 is required BEFORE launch. Build101 lacked it.
K32_SRC="$ROOT/wine/build-bootstrap-pe/dlls/kernel32/aarch64-windows/kernel32.dll"
K32_DST="$ROOT/app/Madeira/aarch64-windows/kernel32.dll"
if [[ ! -s "$K32_SRC" ]]; then
  echo "Missing ARM64 kernel32 source: $K32_SRC" >&2
  exit 4
fi
python3 - "$K32_SRC" <<'PY_CHECK_PE'
from pathlib import Path
import struct, sys
b=Path(sys.argv[1]).read_bytes()
if len(b)<256 or b[:2]!=b"MZ":
    raise SystemExit("kernel32 is not a PE binary")
pe=struct.unpack_from("<I",b,0x3c)[0]
if pe+26>len(b) or b[pe:pe+4]!=b"PE\0\0":
    raise SystemExit("kernel32 invalid PE signature")
machine=struct.unpack_from("<H",b,pe+4)[0]
if machine!=0xaa64:
    raise SystemExit(f"kernel32 expected ARM64 (AA64), got {machine:04x}")
print("PASS ARM64 kernel32 PE architecture")
PY_CHECK_PE
if ! cmp -s "$K32_SRC" "$K32_DST"; then
  mkdir -p "$WORK/build103-artifacts/backup"
  if [[ -s "$K32_DST" ]]; then
    cp -pn "$K32_DST" "$WORK/build103-artifacts/backup/kernel32.dll.previous"
  fi
  cp -p "$K32_SRC" "$K32_DST"
fi
for pe in aarch64-windows/kernel32.dll aarch64-windows/kernelbase.dll; do
  [[ -s "$ROOT/app/Madeira/$pe" ]] || { echo "MISSING $pe" >&2; exit 4; }
done

# Build103 ARM64 DLL closure (observed missing in Build102 runtime).
export PATH="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
DLLS=(rpcrt4 user32 gdi32 advapi32 ucrtbase)
TARGETS=()
for dll in "${DLLS[@]}"; do TARGETS+=("dlls/$dll/aarch64-windows/$dll.dll"); done
make -C "$ROOT/wine/build-bootstrap-pe" -j"${WINE_PE_JOBS:-2}" "${TARGETS[@]}"
python3 - "$ROOT" "${DLLS[@]}" <<'PY_DLL_CHECK'
import sys,struct,shutil
from pathlib import Path
root=Path(sys.argv[1])
for name in sys.argv[2:]:
    src=root/'wine/build-bootstrap-pe/dlls'/name/'aarch64-windows'/(name+'.dll')
    b=src.read_bytes()
    if len(b)<256 or b[:2]!=b'MZ': raise SystemExit('missing PE '+name)
    off=struct.unpack_from('<I',b,0x3c)[0]
    if b[off:off+4]!=bytes([80,69,0,0]) or struct.unpack_from('<H',b,off+4)[0]!=0xaa64:
        raise SystemExit('expected ARM64 PE '+name)
    dst=root/'app/Madeira/aarch64-windows'/(name+'.dll')
    shutil.copy2(src,dst)
    print('PASS',name,'ARM64',len(b),'bytes')
PY_DLL_CHECK

# Follow static ARM64 PE imports recursively; build any further modules before IPA.
python3 "$ROOT/tools/diagnostics/build-wine-pe-closure.py" \
  --root "$ROOT" --arch aarch64-windows --jobs "${WINE_PE_JOBS:-2}"

# Fail before Xcode if the observed runtime DLLs are absent or PE imports remain unresolved.
python3 "$ROOT/tools/diagnostics/wine-pe-closure.py" \
  --root "$ROOT" --arch aarch64-windows \
  --require-runtime rpcrt4 --require-runtime user32 \
  --require-runtime gdi32 --require-runtime advapi32 \
  --require-runtime ucrtbase --strict \
  --json "$WORK/diagnostics/build103-arm64-pe-closure-postbuild.json"

# The app requires an actual Wine registry/skeleton archive, never a dummy.
# Build it from a fresh host wineboot inside the external SSD if absent.
PREFIX="$ROOT/app/Madeira/prefix-template.tar.gz"
if ! python3 "$ROOT/tools/dev-build101/build100-preflight.py" --verify-prefix "$PREFIX"; then
  echo "=== Build103: rebuilding missing or INVALID Wine prefix template ==="
  # Prefer the already-staged upstream WineHQ 11.0 package on external APFS.
  # Do not install Homebrew's disabled cask or weaken Gatekeeper settings.
  BUNDLED_WINE="$ARTIFACTS/toolchains/wine-stable-11.0_1/Wine Stable.app/Contents/Resources/wine/bin"
  if [[ -z "${WINE:-}" && ! -x /opt/homebrew/bin/wine && -x "$BUNDLED_WINE/wine" ]]; then
    export WINE="$BUNDLED_WINE/wine"
    if [[ -z "${WINEBOOT:-}" ]]; then export WINEBOOT="$BUNDLED_WINE/wineboot"; fi
  fi
  if [[ -z "${WINEBOOT:-}" && ! -x /opt/homebrew/bin/wineboot && -x "$BUNDLED_WINE/wineboot" ]]; then
    export WINEBOOT="$BUNDLED_WINE/wineboot"
  fi
  echo "Host Wine: ${WINE:-/opt/homebrew/bin/wine}"
  echo "Host wineboot: ${WINEBOOT:-/opt/homebrew/bin/wineboot}"
  # This vendor macOS Wine binary is x86_64 on Apple Silicon.
  if [[ "${WINE:-}" == "$BUNDLED_WINE/wine" ]]; then
    if ! arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
      echo "Rosetta 2 is required to run bundled WineHQ x86_64 on Apple Silicon." >&2
      echo "Install it manually if you approve: softwareupdate --install-rosetta --agree-to-license" >&2
      echo "No system component has been installed automatically." >&2
      exit 4
    fi
  fi
  mkdir -p "$ARTIFACTS/tmp"
  set +e
  PREFIX_BUILD_TMP_BASE="$ARTIFACTS/tmp" \
    bash "$ROOT/tools/build-prefix-snapshot.sh" 2>&1 | tee "$OUT/Build103-prefix-snapshot.log"
  prefix_rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$prefix_rc" -ne 0 ]] || ! python3 "$ROOT/tools/dev-build101/build100-preflight.py" --verify-prefix "$PREFIX"; then
    echo "FAILED: a valid Wine prefix snapshot could not be generated." >&2
    echo "See $OUT/Build103-prefix-snapshot.log; do not use an empty tarball." >&2
    exit 4
  fi
fi
sh "$ROOT/tools/check-prefix-template.sh" "$PREFIX"
# Re-audit after prefix generation, before Xcode allocates compiler outputs.
python3 "$ROOT/tools/dev-build101/build100-preflight.py" \
  --repo "$ROOT" --no-discover --require-ready \
  --output "$WORK/diagnostics/mac-build103-preflight.json"

# 'Sign bundled dylibs' requires two current GPL/exceptions files under
# app/Madeira/licenses; stage them from canonical project sources now so Xcode
# copies the correct folder resources during this incremental build.
bash "$ROOT/build/stage-licenses.sh"
for pair in COPYING:LICENSE-MADEIRA-GPL-3.0.txt LICENSE-EXCEPTION.md:LICENSE-MADEIRA-EXCEPTION.txt; do
  src="$ROOT/${pair%%:*}"
  dst="$ROOT/app/Madeira/licenses/${pair##*:}"
  if ! cmp -s "$src" "$dst"; then
    echo "Build103 license staging failed for: ${pair##*:}" >&2
    exit 4
  fi
done

# iDeck control helper is built by the 'Bundle Wine Mono' Xcode phase. Xcode
# does not infer this project-local cross toolchain from the login shell PATH.
# Export a deterministic LLVM_MINGW path to all shell build phases (and also
# pass it as a build setting below), without changing the global Mac PATH.
if [[ -z "${LLVM_MINGW:-}" ]]; then
  LLVM_MINGW="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal"
fi
CONTROL_CC="$LLVM_MINGW/bin/x86_64-w64-mingw32-clang"
if [[ ! -x "$CONTROL_CC" ]]; then
  echo "Missing LLVM-MinGW x64 compiler: $CONTROL_CC" >&2
  exit 4
fi
export LLVM_MINGW
echo "Build103 x64 Windows helper compiler: $CONTROL_CC"

# Automatic signing must create/use profiles for both <bundle> and
# <bundle>.JITHelper; previous Personal Team rejected original app identifier.
LOG="$OUT/Build103-xcodebuild.log"
echo "Building Debug IPA (without SwiftUI preview dylibs). Xcode build log: $LOG"
set +e
xcodebuild \
  -project "$ROOT/app/Madeira.xcodeproj" \
  -scheme Madeira \
  -configuration Debug \
  -sdk iphoneos \
  -destination "generic/platform=iOS" \
  -derivedDataPath "$DERIVED" \
  -jobs 2 \
  -allowProvisioningUpdates \
  LLVM_MINGW="$LLVM_MINGW" \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM="$TEAM" \
  MADEIRA_BUNDLE_IDENTIFIER="$BUNDLE" \
  CURRENT_PROJECT_VERSION=103 \
  MARKETING_VERSION=0.1.3 \
  ENABLE_DEBUG_DYLIB=NO \
  build 2>&1 | tee "$LOG"
rc="${PIPESTATUS[0]}"
set -e
if [[ "$rc" -ne 0 ]]; then
  echo "Xcode build FAILED (exit $rc). Read $LOG and fix the first build error."
  exit "$rc"
fi

APP="$DERIVED/Build/Products/Debug-iphoneos/Madeira.app"
HELPER="$APP/PlugIns/MadeiraJITHelper.appex"
if [[ ! -d "$APP" || ! -d "$HELPER" ]]; then
  echo "Xcode succeeded but the main app or JITHelper extension is missing."
  exit 4
fi
INFO="/usr/libexec/PlistBuddy"
main_id="$("$INFO" -c 'Print :CFBundleIdentifier' "$APP/Info.plist")"
helper_id="$("$INFO" -c 'Print :CFBundleIdentifier' "$HELPER/Info.plist")"
build_no="$("$INFO" -c 'Print :CFBundleVersion' "$APP/Info.plist")"
if [[ "$main_id" != "$BUNDLE" || "$helper_id" != "$BUNDLE.JITHelper" || "$build_no" != "103" ]]; then
  echo "Unexpected signed bundle or build number. NOT packaging."
  printf 'main=%s helper=%s build=%s\n' "$main_id" "$helper_id" "$build_no"
  exit 5
fi
codesign --verify --strict --verbose=2 "$APP"
codesign --verify --strict --verbose=2 "$HELPER"

STAGE="$(mktemp -d "$OUT/.stage.XXXXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/Payload"
ditto "$APP" "$STAGE/Payload/Madeira.app"
IPA="$OUT/iDeck-WoW64-Build103-Debug.ipa"
(cd "$STAGE" && /usr/bin/ditto -c -k --sequesterRsrc --keepParent Payload "$IPA")
if [[ ! -s "$IPA" ]]; then
  echo "IPA packaging failed."
  exit 6
fi
shasum -a 256 "$IPA" > "$IPA.sha256"
echo "BUILD103 IPA CREATED: $IPA"
echo "SHA256: $(cat "$IPA.sha256")"
echo "No iPhone installation was attempted."
