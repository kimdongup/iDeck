/* SPDX-License-Identifier: GPL-3.0-or-later
 * Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
 * Bounds for the opt-in region-C CEF image experiment. No mapping effects. */
#ifndef IOS_CEF_LOW_IMAGE_POLICY_H
#define IOS_CEF_LOW_IMAGE_POLICY_H

#include <stddef.h>

#define IOS_LOW_SMALL_MAX ((size_t)16 * 1024 * 1024)
#define IOS_LOW_CEF_MAX ((size_t)224 * 1024 * 1024)
#define IOS_LOW_CEF_RESERVE ((size_t)20 * 1024 * 1024)

static inline int ios_low_cef_name(const char *name)
{
    static const char expected[] = "libcef.dll";
    size_t i;
    if (!name) return 0;
    for (i = 0; i < sizeof(expected); ++i)
    {
        unsigned char c = (unsigned char)name[i];
        if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
        if (c != expected[i]) return 0;
        if (!c) return 1;
    }
    return 0;
}

/* 0: refused; 1: unchanged small-image policy; 2: bounded CEF experiment.
 * The CEF path keeps room for a 16MiB FEX code buffer plus a 4MiB margin. */
static inline int ios_low_image_policy(size_t want, const char *name,
                                       int small_enabled, int cef_enabled,
                                       size_t *reserve)
{
    if (!want || (want & 0x3fff)) return 0;
    if (want <= IOS_LOW_SMALL_MAX)
    {
        if (!small_enabled) return 0;
        *reserve = (size_t)4 * 1024 * 1024;
        return 1;
    }
    if (!cef_enabled || want > IOS_LOW_CEF_MAX || !ios_low_cef_name(name)) return 0;
    *reserve = IOS_LOW_CEF_RESERVE;
    return 2;
}

/* Subtract before adding so untrusted sizes cannot wrap the atomic cursor. */
static inline int ios_low_image_fits(size_t total, size_t used, size_t want, size_t reserve)
{
    return total >= reserve && want <= total - reserve && used <= total - reserve - want;
}
#endif
