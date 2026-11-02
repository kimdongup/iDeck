#!/bin/bash
# Install and launch signed iDeck Build113 IPA on an explicitly selected iPhone.
set -euo pipefail
ROOT="${BUILD113_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
IPA="${BUILD113_IPA:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/build113-artifacts/Output/iDeck-WoW64-Build113-Debug.ipa}"
DEVICE="${1:-}"
if [[ "$(uname -s)" != Darwin ]]; then echo "Must run on macOS" >&2; exit 2; fi
if [[ -z "$DEVICE" ]]; then
  echo "Usage: $0 DEVICE_IDENTIFIER" >&2
  echo "Find identifier using: xcrun devicectl list devices" >&2
  exit 2
fi
[[ -s "$IPA" ]] || { echo "Missing IPA: $IPA" >&2; exit 3; }
TMP="$(mktemp -d "${TMPDIR:-/tmp/}ideck-build113.XXXXXXXX")"
trap 'rm -rf "$TMP"' EXIT
ditto -x -k "$IPA" "$TMP"
APP="$TMP/Payload/Madeira.app"
[[ -d "$APP" ]] || { echo "Missing app in IPA" >&2; exit 4; }
python3 "$ROOT/tools/dev-build101/verify-build107-arm64x.py" "$APP/arm64ec-windows/ntdll.dll"
INFO=/usr/libexec/PlistBuddy
BUILD="$("$INFO" -c 'Print :CFBundleVersion' "$APP/Info.plist")"
BUNDLE="$("$INFO" -c 'Print :CFBundleIdentifier' "$APP/Info.plist")"
[[ "$BUILD" == 113 && "$BUNDLE" == com.kimdongup.ideck.build100 ]] || {
  echo "Unexpected app build $BUILD or id $BUNDLE" >&2; exit 5;
}
echo "Installing $BUNDLE build $BUILD to device $DEVICE"
xcrun devicectl device install app --device "$DEVICE" "$APP"
echo "Launching $BUNDLE"
xcrun devicectl device process launch --device "$DEVICE" "$BUNDLE"
echo "Launch command completed; inspect iPhone runtime logs for child boot result."
