#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Compile the actual native-hold adoption helper with ownership/failure fixtures."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
s=(root/"build/ntdll-unix/virtual_ios.c").read_text()
start=s.index("static int ios_cef64_adopt_regular(")
body=s[start:s.index("\n}\n",start)+2]
assert s.count("else if (ios_cef64_adopt_regular(")==1
fixture=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef unsigned long SIZE_T,ULONG_PTR;typedef unsigned ULONG;typedef unsigned NTSTATUS;
typedef uint64_t mach_vm_address_t,mach_vm_size_t;typedef int kern_return_t,mach_port_t,mach_msg_type_number_t;
typedef struct {int protection,max_protection;} vm_region_basic_info_data_64_t;
typedef vm_region_basic_info_data_64_t *vm_region_info_t;
#define MEM_RESERVE 0x2000
#define PAGE_NOACCESS 1
#define VM_REGION_BASIC_INFO_COUNT_64 2
#define VM_REGION_BASIC_INFO_64 9
#define MACH_PORT_NULL 0
#define KERN_SUCCESS 0
#define VM_PROT_NONE 0
#define VM_PROT_READ 1
#define VM_PROT_WRITE 2
#define STATUS_CONFLICTING_ADDRESSES 0xc0000018U
#define STATUS_NO_MEMORY 0xc0000017U
#define dprintf(...) ((void)0)
struct file_view {void *base;size_t size;};static struct file_view result_view;
static const char *config_dir="/private/test/wine-steam64";
static int state=1,held=1,helper=1,wow=0,view_exists,claimed,claims,rollbacks,creates,region_mode,ports;
static NTSTATUS create_status;
static uint64_t hold_base=0x7100000000ULL,hold_size=0x40000000ULL;
static int madeira_cef64_hold_state(void){return state;}
static int madeira_cef64_hold_get(unsigned slot,uint64_t *base,uint64_t *size){assert(slot==0);*base=hold_base;*size=hold_size;return held;}
static int madeira_cef64_hold_claim(unsigned slot){assert(slot==0);claims++;if(claimed)return 0;claimed=1;return 1;}
static void madeira_cef64_hold_unclaim(unsigned slot){assert(slot==0);claimed=0;rollbacks++;}
static int is_wow64(void){return wow;}
static int ios_sc_current_is_helper(void){return helper;}
static void *find_view_range(void *base,size_t size){assert((uint64_t)(uintptr_t)base==hold_base&&size==hold_size);return view_exists?&result_view:NULL;}
static int mach_task_self(void){return 1;}
static int mach_vm_region(int task,mach_vm_address_t *address,mach_vm_size_t *size,int flavor,vm_region_info_t info,mach_msg_type_number_t *count,mach_port_t *port){
 (void)task;(void)flavor;(void)count;*size=0x8000000;*port=1;
 info->protection=region_mode==1?1:0;info->max_protection=region_mode==2?1:3;
 if(region_mode==3)*address+=0x1000;
 return region_mode==4?1:0;
}
static void mach_port_deallocate(int task,mach_port_t port){(void)task;assert(port==1);ports++;}
static NTSTATUS create_view(struct file_view **out,void *base,size_t size,unsigned vprot){
 assert((uint64_t)(uintptr_t)base==hold_base&&size==hold_size&&vprot==0);creates++;
 if(!create_status){result_view=(struct file_view){base,size};*out=&result_view;}return create_status;
}
'''+body+r'''
static int attempt(void **base,ULONG_PTR lo,ULONG_PTR hi,ULONG_PTR alignment,NTSTATUS *status){
 struct file_view *view=NULL;return ios_cef64_adopt_regular(&view,base,0x40000000,MEM_RESERVE,PAGE_NOACCESS,0,lo,hi,alignment,0,status);
}
int main(void){
 void *base=NULL;NTSTATUS status=0x1234;
 assert(!attempt(&base,0,0,0,&status)&&!claims);
 setenv("MADEIRA_CEF_OWNED_REGULAR","1",1);setenv("MADEIRA_STEAM_UI_SESSION","1",1);setenv("MADEIRA_CEF64_SOURCE_LAYOUT","1",1);
 held=0;assert(!attempt(&base,0,0,0,&status)&&!claims);held=1;
 helper=0;assert(!attempt(&base,0,0,0,&status)&&!claims);helper=1;
 wow=1;assert(!attempt(&base,0,0,0,&status)&&!claims);wow=0;
 config_dir="/private/test/other";assert(!attempt(&base,0,0,0,&status)&&!claims);config_dir="/private/test/wine-steam64";
 base=(void *)(uintptr_t)0x70c0000000ULL;assert(!attempt(&base,0,0,0,&status)&&!claims);base=NULL;
 assert(!attempt(&base,hold_base+1,0,0,&status)&&!claims);
 assert(!attempt(&base,0,hold_base+hold_size-2,0,&status)&&!claims);
 assert(!attempt(&base,0,0,0x200000000ULL,&status)&&!claims);
 for(region_mode=1;region_mode<=4;region_mode++)assert(!attempt(&base,0,0,0,&status)&&!claims&&!creates);
 region_mode=0;view_exists=1;assert(attempt(&base,0,0,0,&status)&&status==STATUS_CONFLICTING_ADDRESSES&&!claims);view_exists=0;
 create_status=STATUS_NO_MEMORY;assert(attempt(&base,0,0,0,&status)&&status==STATUS_NO_MEMORY&&!claimed&&rollbacks==1);
 create_status=0;base=(void *)(uintptr_t)0x7c82c0000000ULL;
 assert(attempt(&base,0,hold_base+hold_size-1,0,&status)&&status==0&&claimed);
 assert((uint64_t)(uintptr_t)base==hold_base&&creates==2&&ports>=16);
 base=NULL;assert(attempt(&base,0,0,0,&status)&&status==STATUS_NO_MEMORY&&creates==2);
 puts("PASS: actual hold adoption, source ownership, fixed/bounds checks, native mapping refusal, duplicate claim and rollback");
}
'''
with tempfile.TemporaryDirectory(prefix="cef-owned-regular-") as temporary:
 p=Path(temporary);(p/"test.c").write_text(fixture)
 subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",str(p/"test.c"),"-o",str(p/"test")],check=True)
 subprocess.run([str(p/"test")],check=True)
