/*
 * Read-only guest-window VA inventory shared by the iOS app and Wine.
 * GPL-3.0-or-later with the Madeira Converter Exception, version 1.
 * The callback reports an occupied kernel region at/after "query"; no
 * reservations or VM protection changes occur in this probe.
 */
#ifndef MADEIRA_WOW_VA_PROBE_H
#define MADEIRA_WOW_VA_PROBE_H

#include <stdint.h>
#include <limits.h>

#define WOW_VA_GUEST_WINDOW (UINT64_C(1) << 32)
#define WOW_VA_LOWER_BOUND  (UINT64_C(1) << 32)

struct wow_va_probe_stats
{
    uint64_t total_free, largest_free, largest_at;
    uint64_t first_aligned, aligned_slots;
    uint64_t visited_regions;
    int complete;
};

/* Return 1 for a region, 0 for end-of-map, -1 on query failure. */
typedef int (*wow_va_probe_next)(void *opaque, uint64_t query,
                                  uint64_t *base, uint64_t *size);

static void wow_va_probe_gap(struct wow_va_probe_stats *out,
                             uint64_t lo, uint64_t hi,
                             uint64_t band_lo, uint64_t band_hi)
{
    uint64_t start, end, first, count, n;

    if (hi <= lo) return;
    out->total_free += hi - lo;
    if (hi - lo > out->largest_free)
    {
        out->largest_free = hi - lo;
        out->largest_at = lo;
    }

    start = lo > band_lo ? lo : band_lo;
    end = hi < band_hi ? hi : band_hi;
    if (end <= start || end - start < WOW_VA_GUEST_WINDOW) return;
    if (start > UINT64_MAX - (WOW_VA_GUEST_WINDOW - 1)) return;
    first = (start + WOW_VA_GUEST_WINDOW - 1) & ~(WOW_VA_GUEST_WINDOW - 1);
    if (first > end || end - first < WOW_VA_GUEST_WINDOW) return;
    count = (end - first) / WOW_VA_GUEST_WINDOW;
    if (!out->first_aligned) out->first_aligned = first;
    n = UINT64_MAX - out->aligned_slots;
    out->aligned_slots += count < n ? count : n;
}

static struct wow_va_probe_stats wow_va_probe_scan(
    uint64_t top, uint64_t band_lo, uint64_t band_hi,
    wow_va_probe_next next, void *opaque)
{
    struct wow_va_probe_stats out = {0};
    uint64_t cursor = WOW_VA_LOWER_BOUND;
    unsigned regions = 0;

    if (!next || top <= cursor) return out;
    while (cursor < top && regions++ < 100000)
    {
        uint64_t base = 0, size = 0, end, lo;
        int result = next(opaque, cursor, &base, &size);

        if (!result)
        {
            wow_va_probe_gap(&out, cursor, top, band_lo, band_hi);
            out.complete = 1;
            return out;
        }
        if (result < 0 || !size || base > UINT64_MAX - size) return out;
        end = base + size;
        if (base > cursor)
        {
            wow_va_probe_gap(&out, cursor, base < top ? base : top,
                             band_lo, band_hi);
        }
        lo = end < top ? end : top;
        if (lo <= cursor) return out; /* malformed/stalled region walk */
        cursor = lo;
        out.visited_regions++;
    }
    out.complete = cursor >= top;
    return out;
}

#endif /* MADEIRA_WOW_VA_PROBE_H */
