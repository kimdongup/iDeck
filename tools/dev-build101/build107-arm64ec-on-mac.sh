#!/bin/bash
# Isolated ARM64EC Wine PE build; intentionally does not touch working bootstrap configuration.
set -euo pipefail
ROOT="${BUILD107_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
B="$ROOT/wine/build-bootstrap-arm64ec-fixed"
SRC="$(dirname "$ROOT")/wine-arm64ec-patched"
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
# Prepare a detached, isolated source worktree. Never patch the pinned Wine submodule.
if [[ ! -d "$SRC/.git" && ! -f "$SRC/.git" ]]; then
  git -C "$ROOT/wine" worktree add --detach "$SRC" HEAD
fi
python3 - "$SRC/include/winnt.h" <<'PY_PATCH'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
changes=[
 ('#if defined(__x86_64__) || defined(__i386__)\n/* On x86, Support old GCC',
  '#if (defined(__x86_64__) || defined(__i386__)) && !defined(__arm64ec__)\n/* On x86, Support old GCC'),
 ('#elif defined(__i386__) || defined(__x86_64__)\n    __asm__ __volatile__( "lock; xchgl',
  '#elif (defined(__i386__) || defined(__x86_64__)) && !defined(__arm64ec__)\n    __asm__ __volatile__( "lock; xchgl'),
 ('#if defined(__x86_64__) || defined(__i386__)\n    for (;;) __asm__ __volatile__( "int $0x29"',
  '#if defined(__aarch64__) || defined(__arm64ec__)\n    register ULONG_PTR val __asm__("x0") = code;\n    for (;;) __asm__ __volatile__( "brk #0xf003" :: "r" (val) : "memory" );\n#elif defined(__x86_64__) || defined(__i386__)\n    for (;;) __asm__ __volatile__( "int $0x29"')
]
for old,new in changes:
    if old in s: s=s.replace(old,new,1)
    elif new not in s: raise SystemExit("Unexpected winnt.h layout: "+old[:60])
p.write_text(s)
print("ARM64EC header compatibility applied in detached worktree")
PY_PATCH
# Madeira iOS port references a generated header four levels above the Wine
# source. An external worktree changes that relative path. Rewrite only in
# the detached source tree to point to the canonical generated header.
python3 - "$SRC" "$ROOT/build/madeira_cfg.h" <<'PY_MADEIRA'
from pathlib import Path
import os,sys
src=Path(sys.argv[1]); target=Path(sys.argv[2])
if not target.is_file(): raise SystemExit("Missing canonical Madeira config: "+str(target))
for rel in ("dlls/ntdll/unix/sync.c","dlls/ntdll/unix/system.c"):
    p=src/rel
    s=p.read_text()
    marker='../../../../build/madeira_cfg.h'
    corrected=os.path.relpath(target,p.parent)
    if marker in s: p.write_text(s.replace(marker,corrected))
    elif corrected not in s: raise SystemExit("Unexpected Madeira include: "+str(p))
    print("Madeira include",rel,"->",corrected)
PY_MADEIRA
# A previous configure may have produced config.status before makedep failed.
# Resume its generated rules without deleting the partial build directory.
if [[ -f "$B/config.status" && ! -f "$B/Makefile" ]]; then
  ( cd "$B" && ./config.status )
fi
if [[ ! -f "$B/Makefile" ]]; then
  mkdir -p "$B"
  ( cd "$B" && "$SRC/configure" \
    --enable-archs=aarch64,arm64ec,i386 --with-mingw=llvm-mingw \
    --without-x --without-vulkan --without-freetype --without-gnutls \
    --disable-tests --enable-winegstreamer )
fi
if ! grep -Eq '^arm64ec_CC = .+clang' "$B/Makefile"; then
    echo "ARM64EC compiler not configured; check $B/config.log"; exit 4
fi
make -C "$B" -j"${WINE_PE_JOBS:-2}" dlls/ntdll/aarch64-windows/ntdll.dll
python3 - "$ROOT" "$B" <<'PY_PE'
import pathlib,struct,sys,shutil
root=pathlib.Path(sys.argv[1]); build=pathlib.Path(sys.argv[2])
src=build/'dlls/ntdll/aarch64-windows/ntdll.dll'
b=src.read_bytes(); off=struct.unpack_from('<I',b,0x3c)[0]
machine=struct.unpack_from('<H',b,off+4)[0]
if b[:2]!=b'MZ' or b[off:off+4]!=b'PE\0\0' or machine not in (0xaa64,0xa641):
    raise SystemExit(f"Expected ARM64X/ARM64EC PE, got {machine:04x}")
# Hybrid ARM64X PE is linked at the aarch64 target when arm64ec is enabled.
# Ensure this is not accidentally a plain ARM64 build before staging it.
makefile=(build/'Makefile').read_text()
if 'PE_ARCHS =  aarch64 arm64ec i386' not in makefile:
    raise SystemExit('Expected ARM64EC-enabled configuration')
dst=root/'app/Madeira/arm64ec-windows/ntdll.dll'
shutil.copy2(src,dst)
print("PASS ARM64EC ntdll",len(b),"bytes ->",dst)
PY_PE
