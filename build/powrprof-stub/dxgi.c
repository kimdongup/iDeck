/* ARM64EC stand-in for libcef's delay-load of dxgi.dll (CreateDXGIFactory1).
 * Build 191 kept steamwebhelper alive and created the 1068x492 window, then
 * a worker hit the delay-load failure hook on dxgi.dll (BRK, STATUS_ILLEGAL_INSTRUCTION).
 * The UI launch forces software rendering, so a failed factory is the fallback
 * Chromium already expects. The export has to exist or the hook aborts the thread. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

__declspec(dllexport) HRESULT WINAPI CreateDXGIFactory1(const void *iid, void **factory)
{
    (void)iid;
    if (factory) *factory = 0;
    return 0x80004002L; /* E_NOINTERFACE */
}
