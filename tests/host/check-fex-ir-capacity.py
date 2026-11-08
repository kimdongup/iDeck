#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Exercise the actual FEX dual allocator guards at reduced capacities.

Extracted allocator code retains its MIT source license. This validates bounds
and integer overflow, not the maximum IR needed by every guest application.
"""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[2]/"FEX/FEXCore/Source/Interface/IR"
emitter=(root/"IREmitter.h").read_text()
start=emitter.index("inline size_t SelectIRHalfCapacity()")
select=emitter[start:emitter.index("\n}\n",start)+2].replace("#ifdef _WIN32","#if 1")
source=(root/"IntrusiveIRList.h").read_text()
start=source.index("class DualIntrusiveAllocator {")
allocator=source[start:source.index("\nclass DualIntrusiveAllocatorMalloc",start)]
fixture=r'''
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <cstdio>
#define LOGMAN_THROW_A_FMT(condition, ...) do { if (!(condition)) throw std::length_error("capacity"); } while (0)
'''+select+"\n"+allocator+r'''
class TestAllocator : public DualIntrusiveAllocator {
    std::unique_ptr<unsigned char[]> storage;
public:
    explicit TestAllocator(size_t size) : DualIntrusiveAllocator(size),storage(new unsigned char[size*2]) {
        Data=reinterpret_cast<uintptr_t>(storage.get()); List=Data+size;
    }
};
int main() {
    const size_t MiB=1024*1024;
    unsetenv("MADEIRA_FEX_IR_HALF_MIB"); assert(SelectIRHalfCapacity()==8*MiB);
    for (const char* value : {"", "0", "1", "02", "2x", "16", "-2"}) {
        setenv("MADEIRA_FEX_IR_HALF_MIB",value,1); assert(SelectIRHalfCapacity()==8*MiB);
    }
    for (const char* value : {"2", "4", "8"}) {
        setenv("MADEIRA_FEX_IR_HALF_MIB",value,1);
        size_t capacity=size_t(value[0]-'0')*MiB; assert(SelectIRHalfCapacity()==capacity);
        TestAllocator allocator(capacity);
        assert(allocator.DataSize()==0 && allocator.ListSize()==0);
        memset(allocator.DataAllocate(32),0x7a,32);
        memset(allocator.ListAllocate(64),0x4b,64);
        assert(!allocator.DataCheckSize(SIZE_MAX) && !allocator.ListCheckSize(SIZE_MAX));
        memset(allocator.DataAllocate(capacity-32),0x2a,capacity-32);
        memset(allocator.ListAllocate(capacity-64),0x3b,capacity-64);
        assert(allocator.DataSize()==capacity && allocator.ListSize()==capacity);
        assert(!allocator.DataCheckSize(1) && !allocator.ListCheckSize(1));
        bool data_rejected=false,list_rejected=false;
        try { allocator.DataAllocate(1); } catch(const std::length_error&) { data_rejected=true; }
        try { allocator.ListAllocate(1); } catch(const std::length_error&) { list_rejected=true; }
        assert(data_rejected && list_rejected);
        allocator.Reset(); assert(allocator.DataSize()==0 && allocator.ListSize()==0);
        assert(reinterpret_cast<uintptr_t>(allocator.DataAllocate(1))==allocator.DataBegin());
        assert(reinterpret_cast<uintptr_t>(allocator.ListAllocate(1))==allocator.ListBegin());
    }
    puts("PASS: actual dual allocator at 2/4/8 MiB, exact bounds, overflow refusal and reset under ASAN/UBSAN");
}
'''
with tempfile.TemporaryDirectory(prefix="fex-ir-capacity-") as temporary:
    p=Path(temporary);(p/"test.cpp").write_text(fixture)
    subprocess.run(["c++","-std=c++20","-Wall","-Wextra","-Werror","-Wno-unused-result","-fsanitize=address,undefined",
                    str(p/"test.cpp"),"-o",str(p/"test")],check=True)
    subprocess.run([str(p/"test")],check=True)
