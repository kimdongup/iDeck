/* SPDX-License-Identifier: GPL-3.0-or-later
 * Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only). */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "../../build/ntdll-unix/ios_cef_low_image_policy.h"

static uint64_t next_value(uint64_t *seed)
{
    *seed ^= *seed << 13;
    *seed ^= *seed >> 7;
    *seed ^= *seed << 17;
    return *seed;
}

int main(void)
{
    const size_t mib = (size_t)1024 * 1024;
    size_t reserve = 123;
    uint64_t seed = UINT64_C(0xdeadbeef12345678);
    unsigned i;

    assert(!ios_low_image_policy(0, "libcef.dll", 1, 1, &reserve));
    assert(!ios_low_image_policy(0xd3d0001, "libcef.dll", 1, 1, &reserve));
    assert(!ios_low_image_policy(0xd3d0000, "libcef.dll", 1, 0, &reserve));
    assert(!ios_low_image_policy(0xd3d0000, "other.dll", 1, 1, &reserve));
    assert(!ios_low_image_policy(0xd3d0000, "libcef.dll.extra", 1, 1, &reserve));
    assert(!ios_low_image_policy(0xd3d0000, NULL, 1, 1, &reserve));
    assert(!ios_low_image_policy(0xd3d0000, "C:\\libcef.dll", 1, 1, &reserve));
    assert(!ios_low_image_policy(16 * mib, "libcef.dll", 0, 1, &reserve));
    assert(ios_low_image_policy(16 * mib, NULL, 1, 0, &reserve) == 1);
    assert(reserve == 4 * mib);
    assert(ios_low_image_policy(0xd3d0000, "LIBCEF.DLL", 0, 1, &reserve) == 2);
    assert(reserve == 20 * mib);
    assert(ios_low_image_policy(224 * mib, "libcef.dll", 0, 1, &reserve) == 2);
    assert(!ios_low_image_policy(224 * mib + 0x4000, "libcef.dll", 0, 1, &reserve));

    /* Recorded Build157 C capacity fits one image with the stronger reserve;
     * a concurrent 16MiB code-buffer carve must make that same request fail. */
    assert(ios_low_image_fits(0x1a000000, 0x1a000000 - 0xeff4000, 0xd3d0000, 20 * mib));
    assert(!ios_low_image_fits(0x1a000000, 0x1a000000 - 0xeff4000 + 16 * mib, 0xd3d0000, 20 * mib));
    assert(ios_low_image_fits(100, 30, 50, 20));
    assert(!ios_low_image_fits(100, 31, 50, 20));
    assert(!ios_low_image_fits(19, 0, 1, 20));
    assert(!ios_low_image_fits(SIZE_MAX, SIZE_MAX, 1, 0));

    for (i = 0; i < 100000; ++i)
    {
        size_t total = (size_t)next_value(&seed), used = (size_t)next_value(&seed);
        size_t want = (size_t)next_value(&seed), guard = (size_t)next_value(&seed);
        int oracle = (__uint128_t)used + want + guard <= (__uint128_t)total;
        assert(ios_low_image_fits(total, used, want, guard) == oracle);
    }
    puts("PASS: opt-in/name/size/alignment gates, recorded capacity, code reserve, overflow and 100000 capacity cases");
    return 0;
}
