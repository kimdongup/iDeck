#!/bin/bash
# Build pinned FEXCore host libraries for iOS ARM64. No FEX upstream edits.
set -eu
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$R/FEX/build-ios"
TC="$R/build/fex-ios/toolchain_ios.cmake"

# The prior failed configure left a CMakeCache but no working Makefile, and
# a CMakeSystem.cmake declaring CMAKE_SYSTEM_PROCESSOR as the empty string.
# Preserve a backup and use --fresh only when the cached platform is invalid.
bad=0
if [ -f "$B/CMakeCache.txt" ] && [ ! -f "$B/Makefile" ] && [ ! -f "$B/build.ninja" ]; then
    bad=1
fi
for sys in "$B"/CMakeFiles/*/CMakeSystem.cmake; do
    if [ -f "$sys" ] && grep -q 'set(CMAKE_SYSTEM_PROCESSOR "")' "$sys"; then
        bad=1
    fi
done

if [ "$bad" -eq 1 ] || [ ! -f "$B/CMakeCache.txt" ]; then
    if [ "$bad" -eq 1 ]; then
        echo "Invalid FEX iOS architecture cache: preserving backup and reconfiguring."
        cp -p "$B/CMakeCache.txt" "$B/CMakeCache.pre-arch-fix.bak"
        # CMake --fresh drops only prior configuration files, not source
        # patches or other platform build directories.
        cmake --fresh -S "$R/FEX" -B "$B" \
            -DCMAKE_TOOLCHAIN_FILE="$TC" -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
            -DCMAKE_OSX_ARCHITECTURES=arm64 \
            -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 \
            -DCMAKE_BUILD_TYPE=Release \
            -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF -DBUILD_FEXCONFIG=OFF \
            -DBUILD_FEX_LINUX_TESTS=OFF -DENABLE_FEX_ALLOCATOR=OFF \
            -DTUNE_CPU=none -DTUNE_ARCH=generic \
            -DENABLE_ASSERTIONS=OFF -DENABLE_CLANG_THUNKS=ON -DENABLE_CCACHE=ON
    else
        cmake -S "$R/FEX" -B "$B" \
            -DCMAKE_TOOLCHAIN_FILE="$TC" -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
            -DCMAKE_OSX_ARCHITECTURES=arm64 \
            -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 \
            -DCMAKE_BUILD_TYPE=Release \
            -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF -DBUILD_FEXCONFIG=OFF \
            -DBUILD_FEX_LINUX_TESTS=OFF -DENABLE_FEX_ALLOCATOR=OFF \
            -DTUNE_CPU=none -DTUNE_ARCH=generic \
            -DENABLE_ASSERTIONS=OFF -DENABLE_CLANG_THUNKS=ON -DENABLE_CCACHE=ON
    fi
fi
# Do not treat CMakeCache.txt alone as a successful build configuration.
if [ ! -f "$B/Makefile" ] && [ ! -f "$B/build.ninja" ]; then
    echo "FEX CMake configure did not generate a build system." >&2
    exit 3
fi
if ! grep -Eq '^set\(CMAKE_SYSTEM_PROCESSOR "(aarch64|arm64)"\)' "$B"/CMakeFiles/*/CMakeSystem.cmake; then
    echo "FEX processor remains unset/wrong after CMake configuration." >&2
    exit 3
fi

# Xcode explicitly links JemallocLibs.a in addition to both FEXCore archives.
# Request its target rather than falsely claiming all seven libraries exist.
cmake --build "$B" --target FEXCore FEXCore_Base JemallocLibs --parallel "${FEX_BUILD_JOBS:-2}"
ls -lh "$B/FEXCore/Source/"*.a
