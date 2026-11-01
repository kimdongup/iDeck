#!/bin/bash
# Builds a minimal Wine prefix snapshot for the iOS app to extract on first launch.
#
# Runs `wineboot --init` on macOS, then strips everything we already ship in the
# app bundle (PE binaries, NLS, fonts). What's left is the registry + directory
# skeleton — the iOS app symlinks bundle resources on top after extraction.
#
# Output: app/Madeira/prefix-template.tar.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT="$REPO_ROOT/app/Madeira/prefix-template.tar.gz"

BUILD_TMP_BASE="${PREFIX_BUILD_TMP_BASE:-/Users/$USER}"
mkdir -p "$BUILD_TMP_BASE"
WORK_DIR="$(mktemp -d "$BUILD_TMP_BASE/madeira-prefix-build.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
PREFIX="$WORK_DIR/prefix"

WINE_BIN="${WINE:-/opt/homebrew/bin/wine}"
WINEBOOT_BIN="${WINEBOOT:-/opt/homebrew/bin/wineboot}"
WINESERVER_BIN="${WINESERVER:-$(dirname "$WINE_BIN")/wineserver}"

if [[ ! -x "$WINE_BIN" ]]; then
    echo "error: wine not found at $WINE_BIN (override with WINE=...)" >&2
    exit 1
fi
if [[ ! -x "$WINEBOOT_BIN" ]]; then
    echo "error: wineboot not found at $WINEBOOT_BIN (override with WINEBOOT=...)" >&2
    exit 1
fi
if [[ ! -x "$WINESERVER_BIN" ]]; then
    echo "error: wineserver not found at $WINESERVER_BIN (override with WINESERVER=...)" >&2
    exit 1
fi

echo "==> Running wineboot --init in $PREFIX"
# Do not silently swallow an unsuccessful initialization (e.g. Rosetta,
# Gatekeeper, missing macOS dylibs, or a failed Wine service).
if ! WINEPREFIX="$PREFIX" WINEARCH=win64 WINEDEBUG=-all \
    "$WINEBOOT_BIN" --init > "$WORK_DIR/wineboot.log" 2>&1; then
    echo "error: wineboot failed; last diagnostics:" >&2
    tail -60 "$WORK_DIR/wineboot.log" >&2
    exit 1
fi
tail -8 "$WORK_DIR/wineboot.log" || true

# wineboot may return before wineserver flushes registry files to disk.
# Stop ONLY the fresh, isolated temporary prefix's server and wait for flush.
echo "==> Flushing Wine registry through wineserver for this temporary prefix"
WINEPREFIX="$PREFIX" "$WINESERVER_BIN" -k >> "$WORK_DIR/wineboot.log" 2>&1 || true
if ! WINEPREFIX="$PREFIX" "$WINESERVER_BIN" -w >> "$WORK_DIR/wineboot.log" 2>&1; then
    echo "error: wineserver did not shut down cleanly" >&2
    tail -60 "$WORK_DIR/wineboot.log" >&2
    exit 1
fi
for reg in system.reg user.reg userdef.reg; do
    if [[ ! -s "$PREFIX/$reg" ]] || ! head -n 1 "$PREFIX/$reg" | grep -q '^WINE REGISTRY Version'; then
        echo "error: missing or uninitialized $reg after wineserver flush" >&2
        tail -60 "$WORK_DIR/wineboot.log" >&2
        exit 1
    fi
done
echo "PASS: all three Wine registry files flushed and initialized."

if [[ ! -f "$PREFIX/.update-timestamp" ]]; then
    echo "error: wineboot did not produce .update-timestamp" >&2
    exit 1
fi

echo "==> Normalizing build-host username to 'madeira'"
# Wine bakes $USER into drive_c/users/$USER and references it from .reg files.
# Rewrite to a stable name so the prefix is portable across build machines.
BUILD_USER="$(id -un)"
if [[ -d "$PREFIX/drive_c/users/$BUILD_USER" && "$BUILD_USER" != "madeira" ]]; then
    mv "$PREFIX/drive_c/users/$BUILD_USER" "$PREFIX/drive_c/users/madeira"
fi
# Fresh host wineboot may create symlinks from shell folders into /Users/...
# Those links become broken after app installation, and the iOS extractor does
# not restore symlink targets. Keep real directories in the portable template.
for shell_folder in Desktop Documents Downloads Music Pictures Videos; do
    user_dir="$PREFIX/drive_c/users/madeira/$shell_folder"
    if [[ -L "$user_dir" ]]; then
        rm "$user_dir"
    fi
    mkdir -p "$user_dir"
done
# Replace both literal `users\BUILD_USER` and any Z:\Users\BUILD_USER host paths.
# The Z:-prefixed ones are host-side fonts Wine auto-registered; stripping the
# whole line is safer than trying to remap — the iOS app ships no Mac fonts.
for reg in "$PREFIX"/system.reg "$PREFIX"/user.reg "$PREFIX"/userdef.reg; do
    [[ -f "$reg" ]] || continue
    # Remove lines pointing into the host's home (Mac fonts, etc.)
    sed -i '' -E "/Z:\\\\\\\\Users\\\\\\\\$BUILD_USER\\\\\\\\/d" "$reg"
    # Rewrite in-prefix paths: both `users\NAME\...` and terminal `users\NAME"`
    sed -i '' -E "s|users\\\\\\\\$BUILD_USER\\\\|users\\\\madeira\\\\|g" "$reg"
    sed -i '' -E "s|users\\\\\\\\$BUILD_USER\"|users\\\\madeira\"|g" "$reg"
    # Bare username (USERNAME= value, and \users\NAME without drive letter)
    sed -i '' -E "s|=\"$BUILD_USER\"|=\"madeira\"|g" "$reg"
    sed -i '' -E "s|\\\\\\\\users\\\\\\\\$BUILD_USER\"|\\\\users\\\\madeira\"|g" "$reg"
done

echo "==> Stripping files shipped in app bundle"
# Drop all PE binaries (iOS app symlinks aarch64 versions from bundle)
find "$PREFIX/drive_c" -type f \( \
    -name "*.dll" -o -name "*.exe" -o -name "*.drv" -o -name "*.sys" \
    -o -name "*.acm" -o -name "*.cpl" -o -name "*.tlb" -o -name "*.ax" \
    -o -name "*.ocx" -o -name "*.mui" -o -name "*.rll" \
    \) -delete

# NLS files are bundled separately in app/Madeira/nls/
find "$PREFIX/drive_c/windows/system32" -maxdepth 1 -name "*.nls" -delete 2>/dev/null || true
rm -rf "$PREFIX/drive_c/windows/globalization"
# Do not include physical Mac host printer descriptions in the IPA.
rm -rf "$PREFIX/drive_c/windows/system32/spool/drivers"
mkdir -p "$PREFIX/drive_c/windows/system32/spool/drivers"

# Heavy trees we don't need for Phase 3A (cmd.exe / single-exe games)
rm -rf "$PREFIX/drive_c/windows/winsxs"
rm -rf "$PREFIX/drive_c/windows/Microsoft.NET"
rm -rf "$PREFIX/drive_c/windows/resources"
rm -rf "$PREFIX/drive_c/windows/system32/catroot"
rm -rf "$PREFIX/drive_c/windows/system32/driverstore"
rm -rf "$PREFIX/drive_c/windows/system32/gecko"
rm -rf "$PREFIX/drive_c/windows/system32/mui"
rm -rf "$PREFIX/drive_c/windows/system32/Speech"
rm -rf "$PREFIX/drive_c/windows/system32/winmetadata"
rm -rf "$PREFIX/drive_c/windows/system32/WindowsPowerShell"
rm -rf "$PREFIX/drive_c/windows/syswow64"

# dosdevices symlinks get recreated by the iOS app (z: -> / is wrong on iOS)
rm -rf "$PREFIX/dosdevices"
# The iOS tar extractor does not recreate symlinks. Remove any remaining
# links from Wine's host layout to keep a portable registry+directory template.
find "$PREFIX" -type l -delete
# Discard AppleDouble / Finder metadata before creating the iOS bundle asset.
find "$PREFIX" -type f \( -name '._*' -o -name '.DS_Store' \) -delete

echo "==> Post-strip contents:"
du -sh "$PREFIX"
find "$PREFIX" -maxdepth 3 -type d | sort

echo "==> Creating tarball (with metadata disabled): $OUTPUT"
# Keep the previous archive untouched unless the new one passes validation.
ARCHIVE_TMP="$WORK_DIR/prefix-template.tar.gz"
COPYFILE_DISABLE=1 tar -C "$WORK_DIR" -czf "$ARCHIVE_TMP" prefix
sh "$REPO_ROOT/tools/check-prefix-template.sh" "$ARCHIVE_TMP"
# Read the archive member table once: grep -q in a pipe can terminate tar
# with SIGPIPE under 'set -o pipefail', yielding a false failure.
tar -tzf "$ARCHIVE_TMP" > "$WORK_DIR/prefix-contents.txt"
for member in system.reg user.reg userdef.reg .update-timestamp; do
    if ! grep -Fqx "prefix/$member" "$WORK_DIR/prefix-contents.txt"; then
        echo "error: $member missing from new Wine archive; preserving existing archive." >&2
        exit 1
    fi
done
if ! grep -Fqx 'prefix/drive_c/windows/system32/' "$WORK_DIR/prefix-contents.txt"; then
    echo "error: system32 directory missing from new archive" >&2
    exit 1
fi
mv -f "$ARCHIVE_TMP" "$OUTPUT"
ls -lh "$OUTPUT"

echo "==> Done."
