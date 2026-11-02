#!/bin/bash
# Install and launch signed iDeck Build121 IPA on an explicitly selected iPhone.
set -euo pipefail
ROOT="${BUILD121_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
IPA="${BUILD121_IPA:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/build121-artifacts/Output/iDeck-WoW64-Build121-Debug.ipa}"
DEVICE="${1:-}"
if [[ "$(uname -s)" != Darwin ]]; then echo "Must run on macOS" >&2; exit 2; fi
if [[ -z "$DEVICE" ]]; then
  echo "Usage: $0 DEVICE_IDENTIFIER" >&2
  echo "Find identifier using: xcrun devicectl list devices" >&2
  exit 2
fi
[[ -s "$IPA" ]] || { echo "Missing IPA: $IPA" >&2; exit 3; }
TMP="$(mktemp -d "${TMPDIR:-/tmp/}ideck-build121.XXXXXXXX")"
trap 'rm -rf "$TMP"' EXIT
ditto -x -k "$IPA" "$TMP"
APP="$TMP/Payload/Madeira.app"
[[ -d "$APP" ]] || { echo "Missing app in IPA" >&2; exit 4; }
if [[ ! -f "$APP/Madeira" ]] || ! LC_ALL=C grep -aFq "[build121-libcef]" "$APP/Madeira"; then
  echo "Build121 IPA missing native diagnostics; refusing to install a stale artifact." >&2
  exit 4
fi
python3 "$ROOT/tools/dev-build101/verify-build107-arm64x.py" "$APP/arm64ec-windows/ntdll.dll"
INFO=/usr/libexec/PlistBuddy
BUILD="$("$INFO" -c 'Print :CFBundleVersion' "$APP/Info.plist")"
BUNDLE="$("$INFO" -c 'Print :CFBundleIdentifier' "$APP/Info.plist")"
[[ "$BUILD" == 121 && "$BUNDLE" == com.kimdongup.ideck.build100 ]] || {
  echo "Unexpected app build $BUILD or id $BUNDLE" >&2; exit 5;
}
echo "Installing $BUNDLE build $BUILD to device $DEVICE"
xcrun devicectl device install app --device "$DEVICE" "$APP"
echo "Launching $BUNDLE"
xcrun devicectl device process launch --device "$DEVICE" "$BUNDLE"
echo "Launch command completed; inspect iPhone runtime logs for child boot result."
