# iDeck FEX native iOS toolchain: the default Apple CMake iOS platform file
# can leave CMAKE_SYSTEM_PROCESSOR empty, which makes this FEX fork's
# CMakeLists.txt:89 string(TOLOWER ...) fail during configuration.
# Set cross-compile processor before project(FEX C CXX ASM) executes.
# Do not modify the pinned FEX submodule.
set(CMAKE_SYSTEM_NAME iOS)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_OSX_ARCHITECTURES arm64 CACHE STRING "Architecture of FEXCore iOS host" FORCE)
