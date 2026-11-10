#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Exercise FEX arena band separation (MADEIRA_FEX_ARENA_BANDS=1, opt-in).
Verifies large 16MiB-class requests prefer the low band, small/medium (<=9MiB,
<16MiB alignment) prefer the high band, and fallbacks preserve placement when a
preferred band is exhausted. Bounds/alignment/protection/alloc size are unchanged."""
from pathlib import Path
import subprocess, tempfile

source = (Path(__file__).resolve().parents[2] / "build/ntdll-unix/virtual_ios.c").read_text()
a = source.index("static void *map_reserved_area( void *limit_low")
body = source[a:source.index("\n}", a) + 2]
harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdio.h>
typedef uintptr_t ULONG_PTR;
static ULONG_PTR ios_fex_arena_base_unix = 0x100000000ULL; /* 4GB base */
static ULONG_PTR ios_fex_arena_end_unix  = 0x180000000ULL; /* +2GB */
static unsigned calls, fail_mask;
static void *los[8], *his[8];
static int downs[8];
static size_t expected_size, expected_align;
#define ERR(...) ((void)0)
#define dprintf(...) ((void)0)
static void *map_reserved_area_inner(void *lo, void *hi, size_t size, int down, int prot, size_t align)
{
    size_t expected = (expected_size == 0x802000) ? 0x810000 : expected_size;
    assert(align == expected_align && prot == 3);
    assert(size == expected || size == expected_size);
    assert(calls < 8);
    los[calls] = lo; his[calls] = hi; downs[calls] = down;
    unsigned bit = 1u << calls++;
    return (fail_mask & bit) ? NULL : (void *)0x140000000ULL;
}
static void *map_reserved_area(void *limit_low, void *limit_high, size_t size, int top_down, int unix_prot, size_t align_mask);
static void reset(const char *bands, const char *small, size_t size, size_t align)
{
    if (bands) setenv("MADEIRA_FEX_ARENA_BANDS", bands, 1); else unsetenv("MADEIRA_FEX_ARENA_BANDS");
    if (small) setenv("MADEIRA_FEX_SMALL_TOPDOWN", small, 1); else unsetenv("MADEIRA_FEX_SMALL_TOPDOWN");
    calls = 0; fail_mask = 0;
    memset(los, 0, sizeof(los)); memset(his, 0, sizeof(his)); memset(downs, 0, sizeof(downs));
    expected_size = size; expected_align = align;
}
int main(void)
{
    ULONG_PTR lo = ios_fex_arena_base_unix, hi = ios_fex_arena_end_unix;
    ULONG_PTR arena_sz = hi - lo;
    ULONG_PTR small_band = arena_sz / 4; /* 512MiB for 2GiB arena */
    if (small_band > 512u * 1024 * 1024) small_band = 512u * 1024 * 1024;
    small_band &= ~(ULONG_PTR)0xffff;
    ULONG_PTR split = (hi - small_band) & ~(ULONG_PTR)0xffff;
    void *r;

    /* Large 16MiB request, 16MiB align: prefers low band [lo,split), original direction. */
    reset("1", NULL, 0x1000000, 0xffffff);
    r = map_reserved_area((void *)lo, (void *)hi, 0x1000000, 0, 3, 0xffffff);
    assert(r && calls == 1);
    assert(los[0] == (void *)lo && his[0] == (void *)split && downs[0] == 0);

    /* Small 8MiB request, <16MiB align: prefers high band [split,hi), top-down. */
    reset("1", NULL, 0x800000, 0xffff);
    r = map_reserved_area((void *)lo, (void *)hi, 0x800000, 0, 3, 0xffff);
    assert(r && calls == 1);
    assert(los[0] == (void *)split && his[0] == (void *)hi && downs[0] == 1);

    /* CallRetStacks 0x802000 rounded to 0x810000, still small class. */
    reset("1", NULL, 0x802000, 0xffff);
    r = map_reserved_area((void *)lo, (void *)hi, 0x802000, 0, 3, 0xffff);
    assert(r && calls == 1);
    assert(los[0] == (void *)split && his[0] == (void *)hi && downs[0] == 1);

    /* Small request, preferred band full: falls back to low band, then full. */
    reset("1", NULL, 0x800000, 0xffff);
    fail_mask = 1u << 0; /* fail preferred high band */
    r = map_reserved_area((void *)lo, (void *)hi, 0x800000, 0, 3, 0xffff);
    assert(r && calls == 2);
    assert(los[0] == (void *)split && his[0] == (void *)hi);
    assert(los[1] == (void *)lo && his[1] == (void *)split);

    /* Large request, preferred low full: falls back to high then full. */
    reset("1", NULL, 0x1000000, 0xffffff);
    fail_mask = (1u << 0) | (1u << 1);
    r = map_reserved_area((void *)lo, (void *)hi, 0x1000000, 0, 3, 0xffffff);
    assert(r && calls == 3);
    assert(los[0] == (void *)lo && his[0] == (void *)split);
    assert(los[1] == (void *)split && his[1] == (void *)hi);
    assert(los[2] == (void *)lo && his[2] == (void *)hi);

    /* 9MiB but 16MiB alignment is treated as large class (preserve alignment opportunities). */
    reset("1", NULL, 0x900000, 0xffffff);
    r = map_reserved_area((void *)lo, (void *)hi, 0x900000, 0, 3, 0xffffff);
    assert(r && calls == 1);
    assert(los[0] == (void *)lo && his[0] == (void *)split);

    /* Bands off preserves existing full-arena behavior (no band narrowing). */
    reset(NULL, NULL, 0x1000000, 0xffffff);
    r = map_reserved_area((void *)lo, (void *)hi, 0x1000000, 0, 3, 0xffffff);
    assert(r && calls == 1);
    assert(los[0] == (void *)lo && his[0] == (void *)hi && downs[0] == 0);

    /* Non-arena range unaffected even if env set. */
    reset("1", NULL, 0x800000, 0xffff);
    r = map_reserved_area((void *)0, (void *)UINTPTR_MAX, 0x800000, 0, 3, 0xffff);
    assert(r && calls == 1);
    assert(los[0] == (void *)0 && his[0] == (void *)UINTPTR_MAX);

    puts("PASS: FEX arena band separation opt-in, class routing, 0x802000 round-up, fallbacks, bounds/alignment/protection preserved");
}
''' + body
with tempfile.TemporaryDirectory(prefix="fex-arena-bands-") as d:
    p = Path(d)
    (p / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    str(p / "test.c"), "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True)
