#!/bin/bash
# Build123 DXMT i386 graphics build. No Wine wined3d substitution.
# Outputs are staged only; packaging is gated by build123-farm.py install.
set -euo pipefail
ROOT="${BUILD123_ROOT:-/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck}"
WORK="$ROOT/../build123-artifacts"
OUT="$WORK/farm/i386-windows"
MODE="${1:---audit}"
if [[ "$MODE" != "--audit" && "$MODE" != "--build" ]]; then
  echo "Usage: $0 [--audit|--build]" >&2; exit 2
fi
TC="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
WINE_BUILD="$ROOT/wine/build-bootstrap-pe"
D="$ROOT/dxmt"
for p in "$WINE_BUILD/Makefile" "$D/meson.build" "$D/build-osx.txt"; do
  [[ -f "$p" ]] || { echo "DXMT prerequisite absent: $p" >&2; exit 3; }
done
if [[ "$MODE" == "--audit" ]]; then
  echo "DXMT source: $D"
  echo "Wine i386 build: $WINE_BUILD"
  echo "Existing Meson setup: $([[ -f "$D/build-pe-i386/build.ninja" ]] && echo yes || echo no)"
  echo "Staging: $OUT"
  exit 0
fi
[[ "$(uname -s)" == Darwin ]] || { echo "DXMT i386 build requires macOS" >&2; exit 2; }
for cmd in meson ninja xcrun; do
  command -v "$cmd" >/dev/null || { echo "Build123 DXMT needs: $cmd" >&2; exit 4; }
done
for cmd in i686-w64-mingw32-clang i686-w64-mingw32-clang++ i686-w64-mingw32-strip; do
  [[ -x "$TC/$cmd" ]] || { echo "Pinned compiler missing: $TC/$cmd" >&2; exit 4; }
done
[[ -x "$WINE_BUILD/tools/winebuild/winebuild" ]] || {
  echo "DXMT requires Wine winebuild at $WINE_BUILD/tools/winebuild/winebuild" >&2
  exit 4
}
export PATH="$TC:$PATH"
export SDKROOT
SDKROOT="$(xcrun --sdk macosx --show-sdk-path)"
mkdir -p "$WORK" "$OUT"
CROSS="$WORK/dxmt-cross-i386.txt"
cat > "$CROSS" <<EOF
[binaries]
c = '$TC/i686-w64-mingw32-clang'
cpp = '$TC/i686-w64-mingw32-clang++'
ar = '$TC/i686-w64-mingw32-ar'
strip = '$TC/i686-w64-mingw32-strip'
windres = '$TC/i686-w64-mingw32-windres'
dlltool = '$TC/i686-w64-mingw32-dlltool'

[properties]
needs_exe_wrapper = true

[host_machine]
system = 'windows'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
EOF
if [[ ! -f "$D/build-pe-i386/build.ninja" ]]; then
  (cd "$D" && meson setup --cross-file "$CROSS" --native-file build-osx.txt \
      --buildtype release -Dwine_build_path="$WINE_BUILD" -Dwine_builtin_dll=true \
      build-pe-i386)
fi
(cd "$D" && meson compile -C build-pe-i386 -j 2)
# Use a temporary file in the staged directory and an atomic rename for every
# output. If DXMT build fails, existing farm files are not modified.
for spec in \
  'd3d11/d3d11.dll:d3d11.dll' \
  'dxgi/dxgi.dll:dxgi.dll' \
  'd3d10/d3d10core.dll:d3d10core.dll' \
  'winemetal/winemetal.dll:winemetal.dll' \
  'd3d9shim/d3d9shim.dll:d3d9.dll' \
  'd3d9shim/d3d9shim.dll:d3d9shim.dll' \
  'd3d9/d3d9.dll:d3d9-emulated.dll'
do
  file="${spec%%:*}"
  dest="${spec#*:}"
  src="$D/build-pe-i386/src/$file"
  [[ -s "$src" ]] || { echo "DXMT output missing: $src" >&2; exit 5; }
  "$TC/i686-w64-mingw32-strip" -o "$OUT/$dest.build123-tmp" "$src"
  mv -f "$OUT/$dest.build123-tmp" "$OUT/$dest"
done
python3 - "$ROOT" <<'PY_VALIDATE'
import importlib.util,sys
from pathlib import Path
root=Path(sys.argv[1])
s=importlib.util.spec_from_file_location('farm',root/'tools/dev-build101/build123-farm.py')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
out=root.parent/'build123-artifacts/farm/i386-windows'
for name in ('dxgi.dll','d3d11.dll','d3d10core.dll','winemetal.dll','d3d9.dll','d3d9shim.dll','d3d9-emulated.dll'):
    info=m.pe_info(out/name)
    print('PASS DXMT PE32',name,info['bytes'],flush=True)
missing=m.REQUIRED['dxgi.dll']-m.pe_info(out/'dxgi.dll')['exports']
if missing:raise SystemExit('DXMT dxgi missing CreateDXGIFactory1: '+str(missing))
PY_VALIDATE
echo 'PASS Build123 DXMT graphics staged; run build123-farm.py install.'
