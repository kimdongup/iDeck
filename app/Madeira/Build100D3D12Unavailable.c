/*
 * Build100D3D12Unavailable.c
 *
 * Explicit, FAIL-CLOSED native D3D12 bridge for an experimental Build100 IPA
 * assembled without Apple's Metal Shader Converter / native IR service.
 *
 * This is NOT an implementation of shader conversion. Do not enable D3D12
 * gaming or claim it is supported in this build. Replace this file in the
 * project Sources phase with madeira-d3d12/src/unix/madeira_ir_unix.mm and its
 * transitive dependencies before enabling native D3D12.
 *
 * The ordinary D3D9/D3D11 DXMT path uses other entry points and is unchanged.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../../madeira-d3d12/src/madeira_ir_abi.h"

/* Keep winemetal's call/return ABI: return 0 to indicate the Unix-call
 * dispatcher executed, but set the conversion result to NO_DYLIB.  Returning
 * a false success in ret_status would be a severe correctness bug. */
int madeira_ir_convert(void *raw_args) {
    if (raw_args == NULL) {
        fprintf(stderr, "[Build100/D3D12] converter unavailable: null request\n");
        return (int)0xC000000DL; /* STATUS_INVALID_PARAMETER */
    }
    struct madeira_ir_convert_args *a = (struct madeira_ir_convert_args *)raw_args;
    a->ret_len = 0;
    a->ret_len2 = 0;
    a->ret_stage = 0;
    a->ret_error_code = 0;
    a->ret_vs_input_count = 0;
    a->ret_loc_count = 0;
    a->ret_status = MADEIRA_IR_NO_DYLIB;
    (void)snprintf(a->ret_note, sizeof(a->ret_note),
                   "Build100: Metal Shader Converter unavailable (D3D12 disabled)");
    fprintf(stderr, "[Build100/D3D12] IR conversion not available; status=NO_DYLIB\n");
    return 0;
}

/* The UI calls this only when madeira.cfg has d3d12=1. An unavailable
 * converter is an actual FAILED gate, not a silently skipped test. */
int madeira_d3d12_canary_run_log(const char *fixture_dir, const char *dylib_path,
                                void (*sink)(const char *), const char *log_path,
                                const char *build_id) {
    (void)fixture_dir;
    (void)dylib_path;
    (void)build_id;
    const char *message =
        "FAIL Build100 D3D12 canary: native IR bridge and Metal Shader Converter "
        "are not built. D3D12 is unavailable in this test IPA.\n";
    if (sink != NULL) sink(message);
    fprintf(stderr, "%s", message);
    if (log_path != NULL && log_path[0] != '\0') {
        FILE *f = fopen(log_path, "w");
        if (f != NULL) {
            fputs(message, f);
            fclose(f);
        } else {
            fprintf(stderr, "[Build100/D3D12] cannot write canary log to %s\n", log_path);
        }
    }
    return 1;  /* explicit failure, never a false PASS */
}

int madeira_d3d12_canary_run(const char *fixture_dir, const char *dylib_path,
                            void (*sink)(const char *)) {
    return madeira_d3d12_canary_run_log(fixture_dir, dylib_path, sink, NULL, NULL);
}
