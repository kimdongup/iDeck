#!/usr/bin/env bash
# Repackage an already compiled and signed Build119 Madeira.app.
# No recompilation, signing, device changes or removal of existing artifacts.
set -euo pipefail
ROOT="${BUILD119_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
WORK="/Volumes/Repository/cokacremote/iDeckRuntimeLab"
BUNDLE="${BUILD119_BUNDLE_ID:-com.kimdongup.ideck.build100}"
ARTIFACTS="$WORK/build100-artifacts"
DERIVED="${BUILD119_DERIVED_DATA:-$ARTIFACTS/DerivedData/iDeckBuild100}"
OUT="${BUILD119_OUTPUT:-$WORK/build119-artifacts/Output}"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Build119 packaging requires macOS (ditto, codesign, PlistBuddy)." >&2
  exit 2
fi
if [[ ! -d "$DERIVED/Build/Products/Debug-iphoneos/Madeira.app" ]]; then
  echo "Build119 compiled app missing; run build119-on-mac.sh --build first." >&2
  exit 3
fi
if [[ ! -d "$OUT" ]]; then
  echo "Build119 output directory absent; must exist after a completed Xcode build: $OUT" >&2
  exit 3
fi
echo "=== Build119 package existing signed app; no rebuild ==="
echo "App: $DERIVED/Build/Products/Debug-iphoneos/Madeira.app"
echo "Output: $OUT"
APP="$DERIVED/Build/Products/Debug-iphoneos/Madeira.app"
HELPER="$APP/PlugIns/MadeiraJITHelper.appex"
# Build119 must ship the exact new native exception diagnostics, not stale DerivedData.
if [[ ! -f "$APP/Madeira" ]] || ! LC_ALL=C grep -aFq "[build119-cef-resolver]" "$APP/Madeira"; then
  echo "Build119 native diagnostic marker missing in Madeira executable; refusing stale IPA." >&2
  exit 5
fi
if [[ ! -d "$APP" || ! -d "$HELPER" ]]; then
  echo "Xcode succeeded but the main app or JITHelper extension is missing."
  exit 4
fi
INFO="/usr/libexec/PlistBuddy"
main_id="$("$INFO" -c 'Print :CFBundleIdentifier' "$APP/Info.plist")"
helper_id="$("$INFO" -c 'Print :CFBundleIdentifier' "$HELPER/Info.plist")"
build_no="$("$INFO" -c 'Print :CFBundleVersion' "$APP/Info.plist")"
if [[ "$main_id" != "$BUNDLE" || "$helper_id" != "$BUNDLE.JITHelper" || "$build_no" != "119" ]]; then
  echo "Unexpected signed bundle or build number. NOT packaging."
  printf 'main=%s helper=%s build=%s\n' "$main_id" "$helper_id" "$build_no"
  exit 5
fi
# Fail closed if Xcode copied stale NTDLL folder resources.
python3 - "$APP" <<'PY_APP_NTDLL'
from pathlib import Path
import sys
app = Path(sys.argv[1])
for arch in ("aarch64-windows", "i386-windows"):
    dll = app / arch / "ntdll.dll"
    if not dll.is_file() or b"[build110-import-fail]" not in dll.read_bytes():
        raise SystemExit(f"Build119 stale or missing traced NTDLL inside signed app: {dll}")
    print(f"PASS Build119 bundled PE trace: {arch}")
PY_APP_NTDLL
for dll in psapi.dll wsock32.dll ncrypt.dll msimg32.dll opengl32.dll winhttp.dll dwrite.dll; do
  if [[ ! -s "$APP/i386-windows/$dll" ]] || ! cmp -s "$ROOT/app/Madeira/i386-windows/$dll" "$APP/i386-windows/$dll"; then
    echo "Build119 missing or stale packaged Steam dependency: $dll" >&2
    exit 5
  fi
done
# Verify that the staged app really contains the intended ARM64X payload.
python3 "$ROOT/tools/dev-build101/verify-build107-arm64x.py" \
  "$APP/arm64ec-windows/ntdll.dll"
cmp -s "$ROOT/app/Madeira/arm64ec-windows/ntdll.dll" \
  "$APP/arm64ec-windows/ntdll.dll" || {
  echo "ARM64X NTDLL was not copied intact into the app bundle." >&2
  exit 5
}
codesign --verify --strict --verbose=2 "$APP"
codesign --verify --strict --verbose=2 "$HELPER"

STAGE="$(mktemp -d "$OUT/.stage.XXXXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/Payload"
ditto "$APP" "$STAGE/Payload/Madeira.app"
IPA="$OUT/iDeck-WoW64-Build119-Debug.ipa"
(cd "$STAGE" && /usr/bin/ditto -c -k --sequesterRsrc --keepParent Payload "$IPA")
if [[ ! -s "$IPA" ]]; then
  echo "IPA packaging failed."
  exit 6
fi
shasum -a 256 "$IPA" > "$IPA.sha256"
echo "BUILD119 IPA CREATED: $IPA"
echo "SHA256: $(cat "$IPA.sha256")"
echo "No iPhone installation was attempted."
