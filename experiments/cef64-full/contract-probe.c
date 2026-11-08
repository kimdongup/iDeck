/* SPDX-License-Identifier: GPL-3.0-or-later
 * Madeira Converter Exception: see ../../LICENSE-EXCEPTION.md (this file only).
 * Load only a caller-selected disposable CEF candidate on a test Windows host.
 * This reports initialization and two public metadata APIs, not Steam success. */
#ifndef UNICODE
#define UNICODE 1
#endif
#ifndef _UNICODE
#define _UNICODE 1
#endif
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef const char *(__cdecl *api_hash_fn)(int);
typedef int (__cdecl *version_info_fn)(int);

static int hash40(const char *value)
{
    unsigned int i;
    if (!value) return 0;
    for (i = 0; i < 40; ++i)
        if (!((value[i] >= '0' && value[i] <= '9') ||
              (value[i] >= 'a' && value[i] <= 'f'))) return 0;
    return value[40] == 0;
}

int wmain(int argc, wchar_t **argv)
{
    const int expected_version[8] = {126, 0, 0, 3171, 126, 0, 6478, 183};
    const char *platform, *universal, *commit;
    int i, match, version[8];
    HMODULE module;
    api_hash_fn api;
    version_info_fn info;
    if (argc != 2 || !((argv[1][0] && argv[1][1] == L':' &&
                        (argv[1][2] == L'\\' || argv[1][2] == L'/')) ||
                       (argv[1][0] == L'\\' && argv[1][1] == L'\\'))) {
        fputs("Supply one absolute disposable libcef.dll path\n", stderr);
        return 64;
    }
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    module = LoadLibraryExW(argv[1], NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!module) {
        printf("{\"load_succeeded\":false,\"win32_error\":%lu}\n", GetLastError());
        return 2;
    }
    api = (api_hash_fn)(void *)GetProcAddress(module, "cef_api_hash");
    info = (version_info_fn)(void *)GetProcAddress(module, "cef_version_info");
    if (!api || !info) return 3;
    platform = api(0); universal = api(1); commit = api(2);
    if (!hash40(platform) || !hash40(universal) || !hash40(commit)) return 3;
    for (i = 0; i < 8; ++i) version[i] = info(i);
    match = !strcmp(platform, "97314fe45c14007fca596262a64cad69467df21f") &&
            !strcmp(universal, "908f7378d71977393cee4bc349055b7365c3673c");
    for (i = 0; i < 8; ++i) match = match && version[i] == expected_version[i];
    printf("{\"load_succeeded\":true,\"platform\":\"%s\",\"universal\":\"%s\","
           "\"commit\":\"%s\",\"version_info\":[", platform, universal, commit);
    for (i = 0; i < 8; ++i) printf("%s%d", i ? "," : "", version[i]);
    printf("],\"baseline_metadata_match\":%s,\"steam_ui_verified\":false}\n", match ? "true" : "false");
    /* Process teardown owns this one loaded module. Avoid a second unload path
     * obscuring the initialization/metadata result in a diagnostic-only tool. */
    return match ? 0 : 4;
}
