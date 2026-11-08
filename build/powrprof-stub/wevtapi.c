/* ARM64EC stand-in for libcef's delay-load of wevtapi.dll.
 * Build 190 loaded powrprof, created the 1068x492 Steam window, then
 * LoadLibrary(wevtapi.dll) failed. The delay-load failure hook raised
 * STATUS_ILLEGAL_INSTRUCTION and crashpad terminated steamwebhelper
 * after 60 seconds, still with the window hidden.
 * These exports fail cleanly so the event-log reader is skipped. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

__declspec(dllexport) void *WINAPI EvtQuery(void *session, const wchar_t *path,
    const wchar_t *query, DWORD flags)
{
    (void)session; (void)path; (void)query; (void)flags;
    SetLastError(ERROR_NOT_SUPPORTED);
    return 0;
}

__declspec(dllexport) BOOL WINAPI EvtNext(void *result, DWORD count, void **events,
    DWORD timeout, DWORD flags, DWORD *returned)
{
    (void)result; (void)count; (void)events; (void)timeout; (void)flags;
    if (returned) *returned = 0;
    SetLastError(ERROR_NO_MORE_ITEMS);
    return FALSE;
}

__declspec(dllexport) BOOL WINAPI EvtRender(void *context, void *fragment, DWORD flags,
    DWORD size, void *buffer, DWORD *used, DWORD *property_count)
{
    (void)context; (void)fragment; (void)flags; (void)size; (void)buffer;
    if (used) *used = 0;
    if (property_count) *property_count = 0;
    SetLastError(ERROR_NOT_SUPPORTED);
    return FALSE;
}

__declspec(dllexport) void *WINAPI EvtCreateRenderContext(DWORD count,
    const wchar_t **values, DWORD flags)
{
    (void)count; (void)values; (void)flags;
    SetLastError(ERROR_NOT_SUPPORTED);
    return 0;
}

__declspec(dllexport) BOOL WINAPI EvtClose(void *handle)
{
    (void)handle;
    return TRUE;
}
