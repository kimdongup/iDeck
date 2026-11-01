#!/bin/bash
# Isolated ARM64EC Wine PE build; intentionally does not touch working bootstrap configuration.
set -euo pipefail
ROOT="${BUILD107_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
B="$ROOT/wine/build-bootstrap-arm64ec"
TC="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
export PATH="$TC:$PATH"
[[ "$(uname -s)" == Darwin ]] || { echo "Run on Mac"; exit 2; }
[[ -x "$TC/arm64ec-w64-mingw32-clang" ]] || { echo "Missing ARM64EC compiler"; exit 2; }
# macOS /usr/bin/bison is often 2.3; Wine requires >=3.0.
if command -v brew >/dev/null 2>&1; then
  BISON_DIR="$(brew --prefix bison 2>/dev/null)/bin" || BISON_DIR=""
  if [[ -n "$BISON_DIR" && -x "$BISON_DIR/bison" ]]; then
    export PATH="$BISON_DIR:$PATH"
  fi
fi
BISON_VERSION="$(bison --version 2>/dev/null | head -1 || true)"
if ! bison --version 2>/dev/null | head -1 | awk '{split($NF,v,"."); exit !(v[1]+0>=3)}'; then
  echo "Wine requires Bison >=3.0; found: ${BISON_VERSION:-none}" >&2
  echo "Install with: brew install bison (script uses brew --prefix bison)" >&2
  exit 3
fi
echo "Bison: $BISON_VERSION"
[[ ! -f "$B/config.status" || -f "$B/Makefile" ]] || { echo "Incomplete ARM64EC configure"; exit 3; }
if [[ ! -f "$B/Makefile" ]]; then
  mkdir -p "$B"
  ( cd "$B" && "$ROOT/wine/configure" \
    --enable-archs=aarch64,arm64ec,i386 --with-mingw=llvm-mingw \
    --without-x --without-vulkan --without-freetype --without-gnutls \
    --disable-tests --enable-winegstreamer )
fi
if ! grep -Eq '^arm64ec_CC = .+clang' "$B/Makefile"; then
    echo "ARM64EC compiler not configured; check $B/config.log"; exit 4
fi
make -C "$B" -j"${WINE_PE_JOBS:-2}" dlls/ntdll/arm64ec-windows/ntdll.dll
python3 - "$ROOT" "$B" <<'PY_PE'
import pathlib,struct,sys,shutil
root=pathlib.Path(sys.argv[1]); build=pathlib.Path(sys.argv[2])
src=build/'dlls/ntdll/arm64ec-windows/ntdll.dll'
b=src.read_bytes(); off=struct.unpack_from('<I',b,0x3c)[0]
machine=struct.unpack_from('<H',b,off+4)[0]
if b[:2]!=b'MZ' or b[off:off+4]!=b'PE\0\0' or machine!=0xa641:
    raise SystemExit(f"Expected ARM64EC PE 0xA641, got {machine:04x}")
dst=root/'app/Madeira/arm64ec-windows/ntdll.dll'
shutil.copy2(src,dst)
print("PASS ARM64EC ntdll",len(b),"bytes ->",dst)
PY_PE
