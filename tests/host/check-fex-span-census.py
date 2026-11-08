#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Compile actual diagnostic and release case, without any real memory release."""
from pathlib import Path
import tempfile,subprocess
s=(Path(__file__).resolve().parents[2]/"build/ntdll-unix/virtual_ios.c").read_text()
a=s.index("static void ios_span_census(");body=s[a:s.index("\n}",a)+2]
a=s.index("    case MEM_RELEASE:\n    {\n        int whole_view;")
release=s[a:s.index("    case MEM_RELEASE |",a)]
assert s.count("if (!st && (type & MEM_RESERVE)) ios_span_census( *ret, *size_ptr, 0 );")==2
assert s.count("ios_span_census( base, size, 1 );")==1
h=r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef uintptr_t ULONG_PTR;
typedef struct { struct {void *UniqueThread;} ClientId;void *Peb; } TEB;
static TEB *NtCurrentTeb(void){return NULL;}
static ULONG_PTR ios_fex_arena_base_unix,ios_fex_arena_end_unix;
static unsigned ios_span_alloc_n,ios_span_free_n,ios_span_event_n,lines,truncated;
static char last[512];
static int output(int fd,const char *format,...)
{assert(fd==2);va_list ap;va_start(ap,format);vsnprintf(last,sizeof(last),format,ap);va_end(ap);lines++;truncated+=strstr(last,"TRUNCATED")!=NULL;return 1;}
#define dprintf output
'''+body+r'''
#define MEM_RELEASE 0x8000
struct view_t {void *base;size_t size;};
static struct {int valid;} ios_vh_free_site;
static int free_result;
static void ios_vh_capture_free_site(struct view_t *v,void *r){(void)v;(void)r;}
static int free_pages(struct view_t *v,void *b,size_t n){(void)v;(void)b;(void)n;return free_result;}
static void exercise_release(void *base,size_t size,struct view_t *view,int type)
{int status=0;switch(type){
'''+release+r'''
default:break;}}
int main(void)
{
 setenv("MADEIRA_FEX_SPAN_TRACE","1",1);
 uintptr_t lo=0x7040920000ULL,hi=lo+0x5b000000;
 const size_t span=0x1000000;
 ios_fex_arena_base_unix=lo;ios_fex_arena_end_unix=hi;
 ios_span_census((void *)lo,span,0);assert(lines==1 && ios_span_alloc_n==1);
 ios_span_census((void *)(hi-span),span,0);assert(lines==2);
 ios_span_census((void *)(lo-1),span,0);
 ios_span_census((void *)(hi-span+1),span,0);
 ios_span_census((void *)hi,span,0);
 ios_span_census((void *)lo,span-1,0);
 ios_span_census((void *)lo,SIZE_MAX,0);
 ios_span_census((void *)UINTPTR_MAX,span,0);assert(lines==2);
 struct view_t view={(void *)lo,span};
 free_result=1;exercise_release((void *)lo,0,&view,MEM_RELEASE);assert(ios_span_free_n==0);
 free_result=0;exercise_release((void *)lo,span/2,&view,MEM_RELEASE);assert(ios_span_free_n==0);
 exercise_release((void *)(lo+1),span-1,&view,MEM_RELEASE);assert(ios_span_free_n==0);
 exercise_release((void *)lo,0,&view,MEM_RELEASE);assert(ios_span_free_n==1);
 ios_fex_arena_base_unix=0x7d00000000ULL;ios_fex_arena_end_unix=0x8000000000ULL;
 ios_span_census((void *)0x7d00000000ULL,span,0);assert(ios_span_alloc_n==3);
 ios_fex_arena_base_unix=0;ios_span_census((void *)lo,span,0);assert(ios_span_alloc_n==3);
 ios_fex_arena_base_unix=lo;ios_fex_arena_end_unix=hi;
 ios_span_alloc_n=ios_span_free_n=ios_span_event_n=lines=truncated=0;
 for(unsigned i=0;i<4100;i++)ios_span_census((void *)lo,span,0);
 assert(lines==4097 && truncated==1 && ios_span_alloc_n==4100);
 puts("PASS: actual census dynamic bounds, overflow, successful whole-release accounting, null TEB and trace cap");
}
'''
with tempfile.TemporaryDirectory(prefix="fex-span-census-") as d:
 p=Path(d);(p/"test.c").write_text(h)
 subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",str(p/"test.c"),"-o",str(p/"test")],check=True)
 subprocess.run([str(p/"test")],check=True)
