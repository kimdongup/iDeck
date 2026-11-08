#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Exercise the actual native placement wrapper: containment, unchanged arguments,
existing direction, opt-in semantics and original-direction failure fallback."""
from pathlib import Path
import subprocess,tempfile
source=(Path(__file__).resolve().parents[2]/"build/ntdll-unix/virtual_ios.c").read_text()
a=source.index("static void *map_reserved_area( void *limit_low")
body=source[a:source.index("\n}",a)+2]
harness=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdio.h>
typedef uintptr_t ULONG_PTR;
static ULONG_PTR ios_fex_arena_base_unix=0x100000000ULL,ios_fex_arena_end_unix=0x180000000ULL;
static unsigned calls,fail_first,fail_all;
static int directions[3];
static void *expected_lo,*expected_hi;
static size_t expected_size,expected_align;
#define ERR(...) ((void)0)
#define dprintf(...) ((void)0)
static void *map_reserved_area_inner(void *lo,void *hi,size_t size,int down,int prot,size_t align)
{
 size_t expected = (expected_size == 0x802000) ? 0x810000 : expected_size;
 assert(lo==expected_lo && hi==expected_hi && (size==expected || size==expected_size) && align==expected_align && prot==3);
 assert(calls<5);directions[calls++]=down;
 return fail_all || (fail_first && calls==1) ? NULL : (void *)0x140000000ULL;
}
'''+body+r'''
static void check(const char *env,uintptr_t lo,uintptr_t hi,size_t size,int down,int first_fail,int all_fail,int first_dir,unsigned count)
{
 if(env)setenv("MADEIRA_FEX_SMALL_TOPDOWN",env,1);else unsetenv("MADEIRA_FEX_SMALL_TOPDOWN");
 calls=0;fail_first=first_fail;fail_all=all_fail;
 expected_lo=(void *)lo;expected_hi=(void *)hi;expected_size=size;expected_align=0xffff;
 void *r=map_reserved_area(expected_lo,expected_hi,size,down,3,expected_align);
 assert(calls==count && directions[0]==first_dir);
 if(count==2)assert(directions[1]==down);
 assert((r==NULL)==(all_fail || (first_fail && count==1)));
}
int main(void)
{
 uintptr_t lo=ios_fex_arena_base_unix,hi=ios_fex_arena_end_unix;
 check(NULL,lo,hi,0x200000,0,0,0,0,1);
 check("0",lo,hi,0x200000,0,0,0,0,1);
 check("true",lo,hi,0x200000,0,0,0,0,1);
 check("1",lo,hi,0x800000,0,0,0,1,1);
 check("1",lo,hi,0x802000,0,0,0,1,1);
 check("1",lo,hi,0x900000,0,0,0,1,1);
 check("1",lo,hi,0x900001,0,0,0,0,1);
 check("1",lo,hi,0,0,0,0,0,1);
 check("1",lo-1,hi,0x200000,0,0,0,0,1);
 check("1",lo,hi+1,0x200000,0,0,0,0,1);
 check("1",0,UINTPTR_MAX,0x200000,0,0,0,0,1);
 check("1",lo,lo,0x200000,0,0,0,0,1);
 check("1",lo,hi,0x200000,1,0,0,1,1);
 check("1",lo,hi,0x200000,0,1,0,1,2);
 check("1",lo,hi,0x200000,0,0,1,1,2);
 check("0",lo,hi,0x200000,0,1,0,0,1);
 ios_fex_arena_base_unix=0;
 check("1",lo,hi,0x200000,0,0,0,0,1);
 puts("PASS: actual placement wrapper, 17 gate/fallback cases, bounds/alignment/protection preserved");
}
'''
with tempfile.TemporaryDirectory(prefix="fex-small-topdown-") as d:
 p=Path(d);(p/"test.c").write_text(harness)
 subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",str(p/"test.c"),"-o",str(p/"test")],check=True)
 subprocess.run([str(p/"test")],check=True)
