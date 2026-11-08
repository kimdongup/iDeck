/* ARM64EC stand-in for the one import crashpad_handler.exe actually uses.
 * Wine's powrprof is built for i386 only, so the x64 handler died in
 * loader_init with c0000135 and Chromium then self-terminated
 * (crashpad_client_win.cc: "crash server failed to launch").
 * CallNtPowerInformation returns STATUS_SUCCESS and zeroes the output.
 * Crashpad uses it for battery state; a successful empty answer lets the
 * handler stay up and serve the crash pipe. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

__declspec(dllexport) LONG WINAPI CallNtPowerInformation(
    int level, void *input, ULONG input_size, void *output, ULONG output_size)
{
    (void)level;
    (void)input;
    (void)input_size;
    if (output && output_size)
        ZeroMemory(output, output_size);
    return 0;
}

/* libcef delay-loads these through the power API sets, which forward to
 * powrprof.dll. A missing export takes the same failure hook as a missing DLL. */
__declspec(dllexport) ULONG WINAPI PowerDeterminePlatformRoleEx(ULONG version)
{
    (void)version;
    return 1; /* PlatformRoleDesktop */
}

__declspec(dllexport) DWORD WINAPI PowerGetActiveScheme(void *user, void **guid)
{
    (void)user;
    if (guid) *guid = 0;
    return ERROR_NOT_SUPPORTED;
}

__declspec(dllexport) DWORD WINAPI PowerReadACValue(void *root, const void *scheme,
    const void *subgroup, const void *setting, void *type, void *buffer, DWORD *size)
{
    (void)root; (void)scheme; (void)subgroup; (void)setting; (void)type; (void)buffer;
    if (size) *size = 0;
    return ERROR_NOT_SUPPORTED;
}

__declspec(dllexport) DWORD WINAPI PowerReadDCValue(void *root, const void *scheme,
    const void *subgroup, const void *setting, void *type, void *buffer, DWORD *size)
{
    (void)root; (void)scheme; (void)subgroup; (void)setting; (void)type; (void)buffer;
    if (size) *size = 0;
    return ERROR_NOT_SUPPORTED;
}
