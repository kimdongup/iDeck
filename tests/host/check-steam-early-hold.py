#!/usr/bin/env python3
"""Compile the exact app-owned pre-JIT reservation function with a fake Mach VM."""
from pathlib import Path
import subprocess, tempfile

root = Path(__file__).resolve().parents[2]
full = (root / "app/Madeira/JITAllocator.c").read_text()
start = full.index("uint64_t madeira_wow_early_base;")
end = full.index("uint64_t jit_available_memory(void)", start)
production = full[start:end]
test_c = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "wow_va_probe.h"
typedef uint64_t mach_vm_address_t, mach_vm_size_t;
typedef int kern_return_t, vm_map_t;
#define KERN_SUCCESS 0
#define KERN_NO_SPACE 3
#define VM_FLAGS_FIXED 0x0
#define VM_PROT_NONE 0
#define VM_PROT_ALL 7
#define VM_INHERIT_COPY 1
#define MEMORY_OBJECT_NULL 0
#define _SC_PAGESIZE 1
#define G (UINT64_C(1) << 30)
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "failed line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static int map_calls, should_reject;
static unsigned long long real_base, real_size;
static uint64_t top = 63*G, occupied_lo, occupied_hi;
static int jit_task_map_range(uint64_t *lo, uint64_t *hi) { *lo=0; *hi=top; return 1; }
static long fake_sysconf(int what) { (void)what; return 0x4000; }
#define sysconf fake_sysconf
static void jit_log(const char *fmt, ...) { (void)fmt; }
static int jit_wow_next_region(void *unused, uint64_t query, uint64_t *base, uint64_t *size) {
    (void)unused;
    if (query < 16*G) { *base = 4*G; *size = 12*G; return 1; }
    if (query < occupied_hi) { *base = occupied_lo; *size = occupied_hi - occupied_lo; return 1; }
    return 0;
}
static kern_return_t mach_vm_map(int task, mach_vm_address_t *base, mach_vm_size_t size,
       uint64_t mask, int flags, int object, uint64_t off, int copy,
       int cur, int max, int inheritance) {
    (void)task;(void)mask;(void)object;(void)off;(void)copy;(void)max;(void)inheritance;
    CHECK(flags == VM_FLAGS_FIXED && cur == VM_PROT_NONE);
    map_calls++;
    if (should_reject) return KERN_NO_SPACE;
    real_base=*base; real_size=size;
    return KERN_SUCCESS;
}
static kern_return_t mach_vm_deallocate(int task, mach_vm_address_t addr, mach_vm_size_t size) {
    (void)task;(void)addr;(void)size;
    return 0;
}
static int mach_task_self(void) { return 1; }
""" + production + r"""
int main(void) {
    occupied_lo = 28*G; occupied_hi=63*G;
    CHECK(!getenv("MADEIRA_WOW_EARLY_HOLD"));
    jit_wow_early_hold_try();
    CHECK(map_calls == 0 && madeira_wow_early_base == 0);
    CHECK(setenv("MADEIRA_WOW_EARLY_HOLD","1",1)==0);
    jit_wow_early_hold_try();
    CHECK(map_calls==1 && madeira_wow_early_base==16*G);
    CHECK(madeira_wow_early_length==4*G+0x4000 && real_size==4*G+0x4000);
    CHECK(real_base==16*G);
    jit_wow_early_hold_try();
    CHECK(map_calls==1); /* idempotent */
    madeira_wow_early_base=0; madeira_wow_early_length=0; map_calls=0;
    occupied_lo = 20*G; /* Only 4GB gap: gate must refuse before kernel mapping. */
    jit_wow_early_hold_try();
    CHECK(map_calls==0 && madeira_wow_early_base==0);
    occupied_lo = 28*G; should_reject=1;
    jit_wow_early_hold_try();
    CHECK(map_calls>=1 && madeira_wow_early_base==0);
    puts("PASS: opt-in only, no-overwrite 4GB+guard, idempotence, 8GB safety gate, kernel rejection fallback");
    return 0;
}
"""
with tempfile.TemporaryDirectory() as t:
    test = Path(t) / "early.c"
    exe = Path(t) / "early"
    test.write_text(test_c)
    subprocess.run(["cc","-std=gnu11","-Wall","-Wextra","-Wno-unused-function",
                    "-Werror","-fsanitize=address,undefined","-I",str(root / "build"),
                    str(test),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=20)
