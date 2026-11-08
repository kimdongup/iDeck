#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Compile actual soft-pool admission/release helpers against the Build177 overlap."""
from pathlib import Path
import tempfile,subprocess
s=(Path(__file__).resolve().parents[2]/"build/ntdll-unix/virtual_ios.c").read_text()
def body(signature):
 a=s.index(signature);return s[a:s.index("\n}",a)+2]
assert s.count("ios_soft_range_taken( candidate, *size_ptr )")==4
assert s.count("ios_soft_candidate( cand_slot, *size_ptr, cand_end, &candidate )")==2
assert s.count("ios_soft_candidate( vslot, *size_ptr, 0x6f00000000ULL, &candidate )")==2
c=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef size_t SIZE_T;
#define PROT_NONE 0
#define dprintf(...) ((void)0)
static struct { uint64_t base,size,committed;unsigned commits,collisions,cage;} ios_soft[8];
static unsigned ios_soft_n,unmaps;
static void *anon_mmap_fixed(void *p,size_t n,int prot,int flags)
{(void)p;(void)n;(void)prot;(void)flags;unmaps++;return p;}
'''+body("static int ios_soft_candidate(")+"\n"+body("static int ios_soft_range_taken(")+"\n"+body("static int ios_soft_release(")+r'''
int main(void)
{
 const uint64_t a=0x7100000000ULL,b=0x7110000000ULL,gb=0x40000000ULL;
 uint64_t candidate=0;
 assert(ios_soft_candidate(0x6000000000ULL,gb+0x10000,0x6f00000000ULL,&candidate));
 assert(candidate==0x603fff0000ULL && !((candidate+0x10000)&(gb-1)));
 assert(ios_soft_candidate(0x6010000000ULL,gb,0x6f00000000ULL,&candidate));
 assert(candidate==0x6040000000ULL && !(candidate&(gb-1)));
 assert(!ios_soft_candidate(a,gb+0x10000,0x7160000000ULL,&candidate));
 assert(!ios_soft_candidate(UINT64_MAX-1,gb,UINT64_MAX,&candidate));
 assert(!ios_soft_candidate(a,0,UINT64_MAX,&candidate));
 ios_soft_n=1;ios_soft[0].base=a;ios_soft[0].size=gb;
 assert(ios_soft_range_taken(b,gb+0x10000)); /* actual Build177 second grant */
 assert(ios_soft_range_taken(a,gb));
 assert(ios_soft_range_taken(a-1,2));
 assert(ios_soft_range_taken(a+gb-1,2));
 assert(!ios_soft_range_taken(a+gb,gb)); /* adjacency is valid */
 assert(!ios_soft_range_taken(a-gb,gb));
 assert(ios_soft_range_taken(a,0));
 assert(ios_soft_range_taken(UINT64_MAX-1,2));
 SIZE_T served=123;
 assert(!ios_soft_release((void *)(uintptr_t)(a+0x10000),&served));
 assert(ios_soft_n==1 && served==123 && !unmaps);
 assert(ios_soft_release((void *)(uintptr_t)a,&served));
 assert(ios_soft_n==0 && served==gb && !unmaps);
 assert(!ios_soft_range_taken(b,gb));
 ios_soft_n=1;ios_soft[0].base=UINT64_MAX-2;ios_soft[0].size=4;
 assert(ios_soft_range_taken(a,gb)); /* malformed recorded range: fail closed */
 ios_soft[0].base=a;ios_soft[0].size=gb;ios_soft[0].committed=0x10000;
 assert(ios_soft_release((void *)(uintptr_t)a,&served));assert(unmaps==1);
 puts("PASS: Build177 overlap rejected; adjacency, overflow and exact-base release preserved");
}
'''
with tempfile.TemporaryDirectory(prefix="soft-pool-regression-") as d:
 p=Path(d);(p/"test.c").write_text(c)
 subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",str(p/"test.c"),"-o",str(p/"test")],check=True)
 subprocess.run([str(p/"test")],check=True)
