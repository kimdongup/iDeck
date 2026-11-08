/* SPDX-License-Identifier: GPL-3.0-or-later
 * Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
 * Read-only discriminator for the pinned CEF126 LogMessage fatal layout.
 */
#ifndef IOS_CEF_FATAL_SITE_H
#define IOS_CEF_FATAL_SITE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef int (*ios_cef_fatal_read_fn)(uint64_t, void *, size_t, void *);
struct ios_cef_fatal_site
{
    const char *file;
    uint32_t line, severity;
};

static int ios_cef_fatal_site_read( uint64_t rip, uint64_t object,
                                  ios_cef_fatal_read_fn read_memory, void *opaque,
                                  struct ios_cef_fatal_site *site )
{
    static const char *const known_files[] = {
        "page_allocator.cc", "page_allocator_internals_win.h",
        "partition_address_space.cc", "address_pool_manager.cc"
    };
    uint64_t file_address = 0;
    uint32_t severity = 0, line = 0;
    unsigned char trap[3];
    char path[256];
    const char *base;
    size_t i;

    memset( site, 0, sizeof(*site) );
    if (!rip || rip > UINT64_MAX - 1 || !object || object > UINT64_MAX - 0x12c)
        return 0;
    if (!read_memory( rip - 1, trap, sizeof(trap), opaque ) ||
        trap[0] != 0xcc || trap[1] != 0x0f || trap[2] != 0x0b)
        return 0;
    if (!read_memory( object + 8, &severity, sizeof(severity), opaque ) || severity != 3 ||
        !read_memory( object + 0x120, &file_address, sizeof(file_address), opaque ) ||
        !read_memory( object + 0x128, &line, sizeof(line), opaque ) || !line || line > 100000 ||
        !file_address || file_address > UINT64_MAX - sizeof(path))
        return 0;
    /* Byte reads tolerate a terminator next to an unreadable page. Never print
     * guest strings: only return one of the constant whitelist labels. */
    for (i = 0; i < sizeof(path); i++)
    {
        if (!read_memory( file_address + i, path + i, 1, opaque )) return 0;
        if (!path[i]) break;
        if ((unsigned char)path[i] < 32 || (unsigned char)path[i] > 126) return 0;
    }
    if (i == sizeof(path)) return 0;
    base = path;
    for (i = 0; path[i]; i++)
        if (path[i] == '/' || path[i] == '\\') base = path + i + 1;
    for (i = 0; i < sizeof(known_files) / sizeof(known_files[0]); i++)
    {
        if (strcmp( base, known_files[i] )) continue;
        site->file = known_files[i];
        site->line = line;
        site->severity = severity;
        return 1;
    }
    return 0;
}
#endif
