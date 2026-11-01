#!/usr/bin/env bash
# Prepare the two native libraries that failed in Build100 ntdll:
#   dwrite_unixlib: FreeType 2.13.3 headers + static library
#   winegstreamer_unixlib: WIDL-generated Wine IDL headers
# Runs on macOS only. Does not clean/replace pre-existing Wine or Xcode data.
set -euo pipefail
R="/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck"
W="$R/wine/build-macos"
LOGDIR="/Volumes/Repository/cokacremote/iDeckRuntimeLab/diagnostics/native-build"
MODE="${1:---plan}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Run on Mac with Xcode, not the Linux container." >&2
  exit 2
fi
case "$MODE" in --plan|--prepare) ;; *) echo "Usage: $0 [--plan|--prepare]" >&2; exit 2;; esac

FT_SRC="$R/research/freetype"
FT_BUILD="$R/build/freetype-ios/build"
FT_LIB="$FT_BUILD/libfreetype.a"
HEADERS=(
  wtypes.h wtypesbase.h
  mfobjects.h mftransform.h
  dwrite.h dwrite_1.h dwrite_2.h dwrite_3.h d2d1.h
  objidlbase.h objidl.h oaidl.h oleidl.h unknwn.h
  ocidl.h propidl.h mfidl.h strmif.h
)
echo "=== Wine ntdll prerequisites — $MODE ==="
if [[ ! -s "$W/include/config.h" || ! -f "$W/Makefile" ]]; then
  echo "Wine config missing; run build100-wine-native-on-mac.sh --configure first." >&2
  exit 3
fi
if [[ ! -f "$FT_SRC/include/ft2build.h" ]]; then
  echo "FreeType source missing: $FT_SRC/include/ft2build.h" >&2
  exit 3
fi
if [[ "$(git -C "$FT_SRC" rev-parse HEAD)" != "42608f77f20749dd6ddc9e0536788eaad70ea4b5" ]]; then
  echo "Wrong FreeType revision. Expected official VER-2-13-3 commit." >&2
  exit 3
fi

echo "FreeType source: pinned VER-2-13-3"
echo "FreeType iOS library: $([[ -s "$FT_LIB" ]] && echo PRESENT || echo MISSING)"
missing=0
for header in "${HEADERS[@]}"; do
  if [[ ! -s "$W/include/$header" ]]; then
    printf '  Missing Wine generated header: %s\n' "$header"
    missing=$((missing+1))
  fi
done
echo "Wine generated headers missing: $missing / ${#HEADERS[@]}"
if [[ "$MODE" == "--plan" ]]; then
  echo "No source files or generated files changed."
  exit 0
fi

mkdir -p "$LOGDIR"
if [[ ! -s "$FT_LIB" ]]; then
  echo "=== Building FreeType 2.13.3 for iOS ==="
  set +e
  bash "$R/build/freetype-ios/build.sh" 2>&1 | tee "$LOGDIR/freetype-ios.log"
  rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$rc" -ne 0 || ! -s "$FT_LIB" ]]; then
    echo "FreeType iOS build failed; check $LOGDIR/freetype-ios.log" >&2
    exit 4
  fi
fi

# Generating only leaf headers left nested WIDL includes unresolved.
# The Wine-generated include/all target covers the complete recursive set.
# This is incremental and avoids a full Wine application/PE build.
echo "=== Generating complete Wine IDL header set (incremental) ==="
set +e
make -C "$W" -j2 include/all 2>&1 | tee "$LOGDIR/wine-generated-headers.log"
rc="${PIPESTATUS[0]}"
set -e
if [[ "$rc" -ne 0 ]]; then
  echo "Wine WIDL header generation failed; check $LOGDIR/wine-generated-headers.log" >&2
  exit 5
fi

for header in "${HEADERS[@]}"; do
  if [[ ! -s "$W/include/$header" ]]; then
    echo "Expected generated Wine header missing: $header" >&2
    exit 5
  fi
done
if [[ ! -s "$FT_LIB" ]]; then
  echo "Expected FreeType library missing after preparation." >&2
  exit 4
fi
if command -v lipo >/dev/null 2>&1; then
  lipo -info "$FT_LIB"
fi
echo "PASS: FreeType iOS lib + ${#HEADERS[@]} WIDL headers ready for Wine ntdll"
