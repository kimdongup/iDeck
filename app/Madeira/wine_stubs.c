// wine_stubs.c - Provide missing symbols for Wine on iOS

#include <CoreFoundation/CoreFoundation.h>

// Wine build version string (normally generated at compile time)
const char wine_build[] = "wine-10.0-ios";

// IOPowerSources stubs - not available on iOS
CFTypeRef IOPSCopyPowerSourcesInfo(void) { return NULL; }
CFArrayRef IOPSCopyPowerSourcesList(CFTypeRef blob) { (void)blob; return NULL; }
CFDictionaryRef IOPSGetPowerSourceDescription(CFTypeRef blob, CFTypeRef ps) {
    (void)blob; (void)ps; return NULL;
}

int madeira_d3d12_canary_run(const char *fixture_dir, const char *dylib_path, void (*sink)(const char *)) {
    return 1;
}

int madeira_d3d12_canary_run_log(const char *fixture_dir, const char *dylib_path,
                                 void (*sink)(const char *), const char *log_path,
                                 const char *build_id) {
    if (sink) sink("D3D12 unavailable\n");
    return 1;
}

int madeira_ir_convert(void *arg) {
    return (int)0xc000000d;
}
