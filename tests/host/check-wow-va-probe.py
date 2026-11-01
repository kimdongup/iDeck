#!/usr/bin/env python3
"""Compile/test the shared, read-only WoW64 hole and aligned-slot census."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
c = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "wow_va_probe.h"
#define G (UINT64_C(1) << 30)
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL %s line %d\n", #x, __LINE__); exit(1); } } while(0)
struct region { uint64_t lo, hi; };
struct scenario { struct region *mapped; unsigned count; int error; };
static int next(void *opaque, uint64_t query, uint64_t *base, uint64_t *size)
{
    struct scenario *s = opaque;
    unsigned i;
    if (s->error) return -1;
    for (i = 0; i < s->count; ++i)
        if (s->mapped[i].hi > query)
        {
            *base = s->mapped[i].lo;
            *size = s->mapped[i].hi - s->mapped[i].lo;
            return 1;
        }
    return 0;
}
int main(void)
{
    /* 63GB task with a large, unoccupied low band. */
    struct region a[] = {{4*G, 16*G}, {48*G, 63*G}};
    struct scenario s = {a, 2, 0};
    struct wow_va_probe_stats p = wow_va_probe_scan(63*G, 16*G, 44*G, next, &s);
    CHECK(p.complete && p.total_free == 32*G);
    CHECK(p.largest_free == 32*G && p.largest_at == 16*G);
    CHECK(p.first_aligned == 16*G && p.aligned_slots == 7); /* 16..44, 7 x4G */

    /* 13GB total free: fragmentation leaves no single 4GB region. */
    struct region b[] = {{4*G, 16*G}, {19*G, 20*G},
                         {23*G, 24*G}, {27*G, 28*G},
                         {31*G, 32*G}, {35*G, 63*G}};
    s = (struct scenario){b, 6, 0};
    p = wow_va_probe_scan(63*G, 16*G, 44*G, next, &s);
    CHECK(p.complete && p.total_free == 15*G);
    CHECK(p.largest_free == 3*G && p.first_aligned == 0 && p.aligned_slots == 0);

    /* 4GB free, but not 4GB-aligned. */
    struct region c[] = {{4*G, 17*G}, {21*G, 63*G}};
    s = (struct scenario){c, 2, 0};
    p = wow_va_probe_scan(63*G, 16*G, 44*G, next, &s);
    CHECK(p.complete && p.total_free == 4*G && p.largest_free == 4*G);
    CHECK(p.first_aligned == 0 && p.aligned_slots == 0);

    /* Exactly 4GB, perfectly aligned; the kernel mapping is not attempted. */
    struct region d[] = {{4*G, 20*G}, {24*G, 63*G}};
    s = (struct scenario){d, 2, 0};
    p = wow_va_probe_scan(63*G, 16*G, 44*G, next, &s);
    CHECK(p.complete && p.total_free == 4*G);
    CHECK(p.first_aligned == 20*G && p.aligned_slots == 1);

    /* Missing the very last region: a clean scan counts the trailing hole. */
    struct region e[] = {{4*G, 40*G}};
    s = (struct scenario){e, 1, 0};
    p = wow_va_probe_scan(63*G, 16*G, 44*G, next, &s);
    CHECK(p.complete && p.total_free == 23*G);
    CHECK(p.first_aligned == 40*G && p.aligned_slots == 1);

    /* A failed kernel query must not masquerade as free address space. */
    s = (struct scenario){e, 1, 1};
    p = wow_va_probe_scan(63*G, 16*G, 44*G, next, &s);
    CHECK(!p.complete && p.total_free == 0 && p.aligned_slots == 0);

    puts("PASS: total/largest free, fragmented 13GB+, unaligned 4GB, aligned 4GB, tail, kernel query error");
    return 0;
}
"""
with tempfile.TemporaryDirectory() as t:
    src = Path(t) / "probe.c"
    exe = Path(t) / "probe"
    src.write_text(c)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(root / "build"),
                    str(src), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=30)
