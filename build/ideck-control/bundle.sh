#!/bin/bash
set -euo pipefail
out=${1:?destination PE path required}
root=$(cd "$(dirname "$0")/../.." && pwd)
compiler=${LLVM_MINGW:+$LLVM_MINGW/bin/}x86_64-w64-mingw32-clang
if ! command -v "$compiler" >/dev/null 2>&1; then
  if [ -f "$root/../build172-artifacts/DerivedData/Build/Products/Debug-iphoneos/Madeira.app/ideck-control.exe" ]; then
    echo "Using existing prebuilt ideck-control.exe from build172-artifacts"
    mkdir -p "$(dirname "$out")"
    cp "$root/../build172-artifacts/DerivedData/Build/Products/Debug-iphoneos/Madeira.app/ideck-control.exe" "$out"
    exit 0
  fi
  echo "error: iDeck control helper requires LLVM_MINGW or x86_64-w64-mingw32-clang on PATH" >&2
  exit 1
fi
mkdir -p "$(dirname "$out")"
"$compiler" -O2 -Wall -Wextra -Werror -municode -mwindows -Wl,--no-insert-timestamp \
  "$root/build/ideck-control/ideck-control.c" -lshell32 -luser32 -ladvapi32 -o "$out"
