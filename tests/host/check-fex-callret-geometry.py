#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Execute the actual guard-emission sequences in a small A64 arithmetic model.

Extracted FEX code retains its MIT license. This checks guard/reset geometry,
not complete JIT instruction selection, SEH, or a guest application's behavior.
"""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]/"FEX"
header=(root/"FEXCore/include/FEXCore/Debug/InternalThreadState.h").read_text()
start=header.index("  static constexpr size_t CALLRET_STACK_SIZE {FEX_CALLRET_STACK_SIZE};")
geometry=header[start:header.index("\n\n  // The low address",start)]
geometry_header=(root/"FEXCore/include/FEXCore/Debug/CallRetStackGeometry.h").read_text()
guards=[]
needle="ldr(TMP1, STATE, offsetof(FEXCore::Core::CpuStateFrame, State.callret_sp_base));"
for relative,expected in (("FEXCore/Source/Interface/Core/JIT/BranchOps.cpp",3),
                          ("FEXCore/Source/Interface/Core/Dispatcher/Dispatcher.cpp",1)):
    text=(root/relative).read_text();pos=0;found=[]
    while True:
        start=text.find(needle,pos)
        if start<0:break
        end=text.index("(void)Bind(&l_callret_ok);",start)+len("(void)Bind(&l_callret_ok);")
        body=text[start:end]
        assert "CALLRET_LIVE_OFFSET" in body and "CALLRET_LIVE_SHIFT" in body and "CALLRET_DEFAULT_OFFSET" in body
        found.append(body);pos=end
    assert len(found)==expected,(relative,len(found))
    guards.extend(found)
core=(root/"FEXCore/Source/Interface/Core/Core.cpp").read_text()
assert "VirtualDontNeed(Thread->CallRetStackBase, TS::CALLRET_STACK_SIZE)" in core
callret=(root/"Source/Windows/Common/CallRetStack.h").read_text()
start=callret.index("struct CallRetStackInfo {");end=callret.index("/* Returns false",start)
get_info=callret[start:end]
fixture=r'''
#include <cassert>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <memory>
#include <vector>
#include "geometry.h"
namespace FEXCore::Core {
struct InternalThreadState {
'''+geometry+r'''
    void *CallRetStackBase{};
};
struct CpuStateFrame { struct { uint64_t callret_sp_base; } State; };
}
namespace FEXCore::Utils { constexpr size_t FEX_PAGE_SIZE=4096; }
'''+get_info+r'''
using TS=FEXCore::Core::InternalThreadState;
namespace ARMEmitter {
enum class Size { i64Bit };
struct ForwardLabel { unsigned id=~0U; };
}
enum Reg { TMP1, REG_CALLRET_SP, STATE };
class Model {
    enum Op {LOAD,ADD,SUB,SHIFT,BRANCH_ZERO};
    struct Insn {Op op;Reg dst,left,right;uint64_t immediate;};
    std::vector<Insn> code;std::vector<size_t> labels;
    void ldr(Reg dst,Reg,size_t){code.push_back({LOAD,dst,STATE,STATE,0});}
    void add(ARMEmitter::Size,Reg dst,Reg left,uint64_t imm){code.push_back({ADD,dst,left,STATE,imm});}
    void sub(ARMEmitter::Size,Reg dst,Reg left,Reg right){code.push_back({SUB,dst,left,right,0});}
    void lsr(ARMEmitter::Size,Reg dst,Reg left,uint64_t imm){code.push_back({SHIFT,dst,left,STATE,imm});}
    int cbz(ARMEmitter::Size,Reg reg,ARMEmitter::ForwardLabel *label){
        if(label->id==~0U){label->id=labels.size();labels.push_back(0);}
        code.push_back({BRANCH_ZERO,reg,reg,STATE,label->id});return 0;
    }
    int Bind(ARMEmitter::ForwardLabel *label){labels.at(label->id)=code.size();return 0;}
public:
'''
for i,body in enumerate(guards):
    fixture+=f"void generate{i}() {{ ARMEmitter::ForwardLabel l_callret_ok;\n{body}\n}}\n"
fixture+=r'''
    uint64_t run(uint64_t base,uint64_t sp) {
        uint64_t regs[3]={0,sp,base};size_t pc=0;
        while(pc<code.size()) {
            auto i=code[pc++];
            switch(i.op) {
            case LOAD:regs[i.dst]=base;break;
            case ADD:regs[i.dst]=regs[i.left]+i.immediate;break;
            case SUB:regs[i.dst]=regs[i.left]-regs[i.right];break;
            case SHIFT:regs[i.dst]=regs[i.left]>>i.immediate;break;
            case BRANCH_ZERO:if(!regs[i.left])pc=labels.at(i.immediate);break;
            }
        }
        return regs[REG_CALLRET_SP];
    }
};
int main() {
#if defined(FEX_IOS_HOST) && defined(ARCHITECTURE_arm64ec)
    static_assert(TS::CALLRET_STACK_SIZE==0x100000);
#else
    static_assert(TS::CALLRET_STACK_SIZE==0x800000);
#endif
    const uint64_t base=0x7090001000ULL,low=base+TS::CALLRET_LIVE_OFFSET;
    const uint64_t high=low+TS::CALLRET_LIVE_SIZE,def=base+TS::CALLRET_DEFAULT_OFFSET;
    FEXCore::Core::InternalThreadState thread;thread.CallRetStackBase=(void *)(uintptr_t)base;
    auto info=GetInfoThread(&thread);
    assert(info.AllocationBase==base-4096 && info.AllocationEnd==base+TS::CALLRET_STACK_SIZE+4096 && info.DefaultLocation==def);
    for(unsigned guard=0;guard<4;guard++) {
        Model model;
        switch(guard){case 0:model.generate0();break;case 1:model.generate1();break;case 2:model.generate2();break;case 3:model.generate3();break;}
        for(uint64_t sp : {uint64_t(0),base-16,base,low-16,low,def,high-16,high,base+TS::CALLRET_STACK_SIZE,UINT64_MAX}) {
            uint64_t result=model.run(base,sp);
            assert(result==((sp>=low&&sp<high)?sp:def));
            assert(result-16>=base && result+16<=base+TS::CALLRET_STACK_SIZE);
        }
        auto storage=std::make_unique<unsigned char[]>(TS::CALLRET_STACK_SIZE);
        uint64_t sp=def;
        for(unsigned depth=0;depth<100000;depth++) {
            sp=model.run(base,sp)-16;
            memset(storage.get()+sp-base,0x5a,16);
        }
        for(unsigned depth=0;depth<100000;depth++) {
            sp=model.run(base,sp);
            volatile unsigned char value=storage[sp-base];(void)value;sp+=16;
        }
    }
    puts("PASS: four actual emitted guards, reservation/default geometry and deep push/pop bounds under ASAN/UBSAN");
}
'''
with tempfile.TemporaryDirectory(prefix="fex-callret-geometry-") as temporary:
    p=Path(temporary);(p/"test.cpp").write_text(fixture);(p/"geometry.h").write_text(geometry_header)
    for compact in (False,True):
        command=["c++","-std=c++20","-Wall","-Wextra","-Werror","-fsanitize=address,undefined"]
        if compact:command += ["-DFEX_IOS_HOST=1","-DARCHITECTURE_arm64ec=1"]
        subprocess.run([*command,str(p/"test.cpp"),"-o",str(p/"test")],check=True)
        subprocess.run([str(p/"test")],check=True)
    (p/"native.c").write_text('#include "geometry.h"\n_Static_assert(FEX_CALLRET_STACK_SIZE == 0x100000u, "native size");\n_Static_assert(FEX_CALLRET_DEFAULT_OFFSET == 0x80000u, "native default");\nint main(void) { return 0; }\n')
    subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-DWINE_IOS=1",str(p/"native.c"),"-o",str(p/"native")],check=True)
    subprocess.run([str(p/"native")],check=True)
