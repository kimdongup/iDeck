# Build 123 — Compatible Wine i386 DLL Farm + DXMT Integration

**Status:** implemented in source; macOS compilation, iPhone installation and CEF BrowserReady are **not yet verified**.

## Objective
Replace repeated missing-delay-load-DLL patch cycles with a checked, broad Wine PE32/i386 user-mode farm while retaining the pinned iDeck runtime, with DXMT graphics DLLs compiled by their intended provider rather than substituting Wine/wined3d DLLs.

This is a **compatible** farm, not every Wine module including drivers, 16-bit binaries or unsupported host bridges.

## Baseline and audit
- Baseline Build122 bundle: 72 .dll files, approximately 81 MiB total i386-windows resource folder.
- Existing Wine build-bootstrap-pe Makefile: 631 explicit i386 user-mode PE DLL/driver/control-panel/codec component targets, 15 skipped by policy, 616 candidates. Targets vary with Wine config.
- Already shipped farm components are preserved, never overwritten by this pipeline.
- Initially absent, required for observed CEF delay-load paths: WTSAPI32.dll, powrprof.dll (API Set alias api-ms-win-power-base-l1-1-0), DXMT dxgi.dll; wevtapi.dll exists and is preserved.
- Pre-existing source changes inside FEX and Wine git submodules are intentionally preserved.

## Entry points
All run on Mac mini with external APFS Repository drive mounted.

**Read-only audit:**
```bash
bash /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck/tools/dev-build101/build123-on-mac.sh --audit
```

**Build and package, with low-memory parallelism on M1 8 GiB:**

The shared Mac has only 8 GiB unified RAM. Set all four independent build
concurrency controls explicitly. The external SSD is for build artifacts,
not a substitute for unified memory or macOS internal swap space. Monitor
Memory Pressure and internal disk free space; do not rely only on external
SSD free space.

```bash
WINE_PE_JOBS=1 BUILD123_FARM_JOBS=1 BUILD123_FARM_BATCH=4 \
BUILD123_DXMT_JOBS=1 BUILD123_XCODE_JOBS=1 \
bash /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck/tools/dev-build101/build123-on-mac.sh --build
```

**Install after success only:**
```bash
bash /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck/tools/dev-build101/build123-install-launch-on-mac.sh 00008130-000451D91A31001C
```

## Implementation
1. Existing Build122 native PE bootstrap and verified wevtapi.dll are reused.
2. `build123-farm.py build` enumerates all supported PE targets, invokes the configured Wine bootstrap Makefile in batches (`make -k -j2`), checks PE Machine=0x014C and PE32, stages **missing** files in `../build123-artifacts/farm/i386-windows`, and records each failed optional target. Existing files are left untouched.
3. Progress and logs survive interrupted runs: `../build123-artifacts/farm/wine-farm-progress.json` and `logs/batch-XXXX.log`. Reruns skip staged successes.
4. `build123-dxmt-on-mac.sh --build` configures Meson using pinned llvm-mingw and existing `wine/build-bootstrap-pe` outputs, builds DXMT i386 `dxgi`, `d3d11`, `d3d10core`, `winemetal` and D3D9 frontend/shim, then stages verified PE32 graphics files.
5. `build123-farm.py install` requires the full-farm progress manifest and the following **real PE exports** before installing staged files: WTSAPI32: WTSFreeMemory/WTSQuerySessionInformationW/WTSRegisterSessionNotification/WTSUnRegisterSessionNotification; powrprof: CallNtPowerInformation/PowerDeterminePlatformRoleEx; wevtapi: EvtQuery/EvtNext/EvtRender/EvtClose/EvtCreateRenderContext; DXMT dxgi: CreateDXGIFactory1. If any are missing, no staged files are installed.
6. New files are atomically added to app/Madeira/i386-windows; existing filenames are never overwritten. Build123 records the hashes of introduced files for IPA verification.
7. Xcode builds bundle version 123; `build123-farm.py verify --app-dir .../Madeira.app` checks the required exports and all introduced hashes before codesign/IPA. The installer repeats this validation before device install.
8. Madeira's existing WineProcessBridge symlinks the i386 farm into `C:\\windows\\syswow64` each session.

## Failure rules
- **Not a success** if any of WTSAPI32/powrprof/wevtapi/DXMT dxgi or required exports are missing, if DXMT cannot build, or if Xcode fails. No stale Build123 IPA is accepted.
- Optional Wine module compile failures are captured in the JSON manifest. They do not automatically block packaging; the published report must state this limitation and should not claim a perfectly complete Wine distro.
- Do **not** copy Wine's own dxgi/d3d11/d3d10core into the farm: the iOS graphics path is DXMT/Metal; Wine/wined3d frontend cannot be assumed compatible.
- Do **not** modify libcef.dll, skip INT3, suppress Chromium NOTREACHED, change FEX exception dispatch, or broaden JIT permissions in this step.
- The build uses the external Repository disk and refuses the farm build when available disk space is below 20 GiB. Optional make failures do not delete prior outputs.

## Device acceptance checklist
1. Built app version 123, signed, with hash-validated PE32/i386 farm.
2. In each CEF helper PEB, verify WTSAPI32.dll and powrprof DLL/API Set resolution; verify DXMT dxgi.dll and CreateDXGIFactory1 resolution.
3. Confirm previous delay-load hook failure RVA `0x4c36732` no longer repeats; if it does, read the changed depth-2 stub RVA and map to the exact delay import descriptor with `analyze-cef-delay-stubs.py`.
4. Verify `BrowserReady`, Steam web rendering, cold launches, and 10-minute stability. Crashpad timeouts remain an independent issue.

## Validation completed before Mac build
- Python syntax compilation, Bash syntax checks, read-only audit on shared Linux workspace.
- Existing Wine bootstrap Makefile supports 631 candidate module rules; actual status remains Mac build **not run**.
- Existing configured DXMT `build-pe-i386/build.ninja` was absent on shared Linux path. Its Mac build may require further environment fixes; this must be reported, not bypassed.
