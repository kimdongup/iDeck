#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Exercise actual capacity selection, pre-write guard and stopping expression.

The emitted instruction-writing fragment comes from the MIT-licensed FEX source.
This checks buffer bounds, not x86 decoding semantics or complete multiblock IR.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "FEX/FEXCore/Source/Interface/Core/Frontend.cpp").read_text()
start = source.index("static size_t SelectDecodedBufferCapacity()")
select = source[start:source.index("\n}\n", start)+2].replace("#ifdef _WIN32", "#if 1")
start = source.index("  LOGMAN_THROW_A_FMT(DecodedSize < DecodedBufferCapacity")
write = source[start:source.index("\n  for (;;) {", start)]
prefix = "      FinalInstruction = "
start = source.index(prefix)
stop = source[start+len(prefix):source.index(";", start)]
assert "DecodedBufferCapacity" in stop and "DefaultDecodedBufferSize" not in stop
assert "sizeof(FEXCore::X86Tables::DecodedInst) * DecodedBufferCapacity" in source

fixture = r'''
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <cstdio>
#define LOGMAN_THROW_A_FMT(condition, ...) do { if (!(condition)) throw std::runtime_error("capacity"); } while (0)
''' + select + r'''
struct DecodedInst { uint64_t PC; char rest[136]; };
static void emit(DecodedInst *DecodedBuffer, size_t DecodedSize, size_t DecodedBufferCapacity, uint64_t PC) {
    DecodedInst *DecodeInst;
''' + write + r'''
}
int main() {
    unsetenv("MADEIRA_FEX_DECODER_COMPACT"); assert(SelectDecodedBufferCapacity()==65536);
    for (const char *value : {"0", "2", "01", "-1", ""}) {
        setenv("MADEIRA_FEX_DECODER_COMPACT",value,1); assert(SelectDecodedBufferCapacity()==65536);
    }
    setenv("MADEIRA_FEX_DECODER_COMPACT","1",1); assert(SelectDecodedBufferCapacity()==4096);
    for (size_t DecodedBufferCapacity : {size_t(4096),size_t(65536)}) {
        auto buffer=std::make_unique<DecodedInst[]>(DecodedBufferCapacity);
        for (size_t MaxInst : {size_t(1),size_t(4095),size_t(4096),size_t(4097),size_t(65536)}) {
            size_t DecodedSize=0,TotalInstructions=0;
            bool FinalInstruction=false;
            while (!FinalInstruction) {
                emit(buffer.get(),DecodedSize,DecodedBufferCapacity,DecodedSize+0x10000);
                ++DecodedSize; ++TotalInstructions;
                FinalInstruction = ''' + stop + r''';
            }
            assert(DecodedSize==(MaxInst<DecodedBufferCapacity?MaxInst:DecodedBufferCapacity));
            assert(buffer[DecodedSize-1].PC==DecodedSize-1+0x10000);
        }
        bool rejected=false;
        try { emit(buffer.get(),DecodedBufferCapacity,DecodedBufferCapacity,0); }
        catch(const std::runtime_error&) { rejected=true; }
        assert(rejected);
    }
    puts("PASS: actual decoder capacity, exact last write, stop limits and pre-write refusal under ASAN/UBSAN");
}
'''
with tempfile.TemporaryDirectory(prefix="fex-decoder-capacity-") as temporary:
    path=Path(temporary)
    (path/"test.cpp").write_text(fixture)
    subprocess.run(["c++","-std=c++20","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",
                    str(path/"test.cpp"),"-o",str(path/"test")],check=True)
    subprocess.run([str(path/"test")],check=True)
