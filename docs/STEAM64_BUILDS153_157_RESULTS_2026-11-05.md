# Steam64 Build153–157: update recovery and remaining CEF memory failure

2026-11-05 HST. Follow-up to [the Build152 handoff](STEAM64_BUILD152_HANDOFF_2026-11-04.md).

**Verified outcome:** adding the missing ARM64EC CryptoAPI providers removed the repeated provider-load failures and allowed the real Steam64 updater to download, extract, install, and verify its update on the existing iPhone prefix. Later packaging fixes allowed Steam UI and CEF initialization to advance. **The login window still does not appear.** Subsequent CEF processes cannot allocate a sufficiently large contiguous JIT image range and fail with `C0000017`.

This is recovery of the update/bootstrap blocker, not completed Steam64, Big Picture, controller, login, or game acceptance.

**Free-account constraint added after these runs:** inspection of the retained signed app entitlements and its provisioning profile found `com.apple.developer.kernel.increased-memory-limit = true`; extended virtual addressing was absent. These executions therefore do not establish operation without the increased-memory entitlement. A comparison with that entitlement absent from the actual code signature is required before claiming compatibility with the user's free-account constraints. Peak reported physical footprint reached 3,817 MB during retries; samples before the first pool-exhaustion event reached 2,929 MB. Contiguous JIT placement and the normal application memory ceiling must both be addressed.

## Test identity and preservation

- Physical iPhone 15 Pro Max, iOS 27.0.1; existing application ID `com.kimdongup.ideck.build149` and helper `.JITHelper` retained.
- Updates were installed over the existing app. The app was never uninstalled and the prefix was not reset. Account/game data and existing files were not deliberately removed.
- Parent source baseline: `kimdongup/iDeck` main `c7422ff265203cb791dda6ea51f7e961305707a8`.
- Wine source: `9129e9684daaeae70da9435e7c6060e59392634e`. FEX source was not edited.
- Each candidate was repackaged from the preceding preserved IPA, beginning with the verified Build152 IPA. Added DLLs were built from the existing Wine source, not downloaded substitutes or renamed stubs.
- **These IPAs are controlled repackages of Build152, not fresh Xcode builds from public main.** The Build149 runtime branch, local Wine/FEX modifications and Build152 native archives were previously preserved separately. Main alone does not reconstruct all of that runtime state.
- Every candidate retained the same `Madeira.debug.dylib` SHA-256: `b4e374367503820a1237485d1e799d3c4ee966bf6f3c8bbd099896378e07a1d8`. Changes were added PE DLLs, app/helper build numbers and the resulting signatures/resource seals.
- Development profiles, helper, debugging entitlement and nested signatures were verified. TLS trust checking and Steam authentication were not weakened.

Original IPAs, signing material, raw device logs, Steam binaries, device identifiers and screenshots remain local. Do not add those private/generated artifacts to a public commit.

## Executed tests

| Build | Added ARM64EC modules | On-device result |
|---|---|---|
| 152 baseline | None | 60-second update timeout, `http error 0`; 52,857 rsaenh and 30,200 dssenh provider-failure messages in the retained run |
| 153 | rsaenh, dssenh | Provider-failure messages fell to zero. Manifest and update downloaded; extraction/install completed. Subsequent Steam UI load failed on other missing modules |
| 154 | ncrypt, wsock32 | Installed but deliberately not executed: ordinal/forwarder audit found missing mswsock |
| 155 | mswsock | ncrypt/WinSock/video64/steamui loading advanced. vgui2_s then failed on missing GUI/session modules |
| 156 | msimg32, opengl32, glu32, wtsapi32, dwmapi | vgui/Steam UI loading advanced; steamwebhelper started. No Fatal Error title or C0000005 text in that captured run. CEF imports still lacked WinHTTP and DWrite |
| 157 | winhttp, jsproxy, dwrite, schannel | Initial libcef mapping succeeded. Later CEF process loads failed because the JIT pool could not fit another large libcef image. Screenshots remained an empty Wine desktop; login not achieved |

Build153 bootstrap evidence, all on 2026-11-05 HST:

- 21:29:01: `Manifest download: finished`.
- 21:29:08: update download complete, 250,911 KB; package extraction began.
- 21:29:29: installing update.
- 21:31:40: `Update complete, launching Steam...`.
- 21:31:42: installation verification complete after updater relaunch.

The updater reported inability to remove two `.old` backup files and continued. No cleanup deletion was attempted. Later runs at 21:43, 21:47 and 21:53 downloaded the manifest, found installed version `1792618285` current, and verified executable checksums. This corroborates repeated manifest access, not repeated full-download acceptance.

These tests used the same evolving prefix. They were not restored-snapshot A/B repetitions: Steam's successful update itself changed the client. No standalone CryptoAPI acquire/hash/random executable was run; the direct evidence is successful real updater progress, mapped rsaenh and disappearance of the prior load-failure loop.

## Proven dependency failures and fixes

1. Build152's HTTP thread `0068 = CHTTPClientThreadPool:0` repeatedly failed `CRYPT_LoadProvider` for `rsaenh.dll`/`dssenh.dll`. The IPA contained only their i386 variants. ARM64EC providers supplied implemented CP entry points; Build153 mapped rsaenh and no longer recorded the failure loop.
2. The updated `steamui.dll` needs `video64.dll`; its FFmpeg `libavformat-62.dll` imports ncrypt. Both video64 and steamui need WSOCK32. Those Wine modules were missing from the 64-bit farm.
3. video64 imports WSOCK32 ordinal **1142**. Wine forwards it to `mswsock.GetAcceptExSockaddrs`; it is a dependency even when no regular import descriptor names mswsock. The target and its implemented export were verified before executing the completed package.
4. `vgui2_s.dll` imports MSIMG32, OPENGL32, WTSAPI32 and dwmapi. GLU32 was also packaged, and OpenGL's delay dependency was linked as a regular import. Existing iOS native code permits OpenGL DLL initialization but returns unsupported for real host GL calls. DLL load success therefore does not establish OpenGL rendering support.
5. `libcef.dll` imports WINHTTP and DWrite. WinHTTP also needs jsproxy. Its five delay imports were converted to regular imports using the existing build script's supported `UNDELAY=1` path with a complete staging farm. The final PE was checked to have no delay imports. Existing iOS DWrite/Schannel native support was retained.

## Remaining blocker: contiguous executable image storage

At Build157's first failing subsequent CEF image load, native diagnostics reported:

| Measurement | Value |
|---|---:|
| Requested image allocation | `0x0d3d0000` = 211.81 MiB |
| Main pool span | `0x37b78000` = 891.47 MiB (span/holes are not all interchangeable free space) |
| Largest main free-list range | `0x0c90c000` = 201.05 MiB |
| Remaining main virgin capacity | `0x05204000` = 82.02 MiB |
| Region C image capacity reported by census | `0x0ebf4000` = 235.95 MiB |
| Raw/aged free-list ranges fitting the image | 0 / 0 |

The sequence is explicit: `[pool-capacity]` → `[jit-pool] EXHAUSTED` → image `.text` protection/copy failure → `libcef.dll` load `C0000017`. The `[dll-missing]` marker is misleading in this case: the file exists and one earlier libcef image mapped successfully. Later loads fail with **no-memory status**, rather than `C0000135` file/import absence.

Reference native source `ios_pool_low_image_range()` only routes failed image copies **up to 16 MiB** into region C, even with `MADEIRA_POOL_LOW_IMAGES=1`. Therefore its 235.95 MiB census value does not mean the existing configuration can place the 211.81 MiB CEF image there. No allocation guard or reuse grace was disabled, and no blind pool-size change was applied.

The first Build157 capture had no C0000005 text. The longer final capture contains secondary C0000005 text during continued retries; do not turn message counts into independent crash counts or attribute these to the earlier update request. The original code-buffer mprotect warning also remains. A normal termination request at the end found the launched PID already absent; the exact reason that host process ended was not established.

## Source changes and repeatable checks

- `build/wine-pe/build-modules.sh`: include all 14 observed missing runtime modules in the default ARM64EC build list.
- `tools/check-wine-crypto-dlls.py`: require implemented CryptoAPI provider exports and real ARM64EC/ARM64X identity. Wine hybrid images may use raw AMD64 headers; their CHPE metadata/code maps are checked. Traverse regular imports, delay imports and export-forwarded modules. `--root` adds CEF/UI dependency roots.
- `tools/check-wine-media-dlls.py`: preserve the existing default machine gate; allow the caller to admit Madeira's native ARM64 ntdll bridge and expose export-forwarder dependencies.
- `tests/host/check-wine-media-dlls.py`: retain default real-farm checks, add explicit fixture-only mode and forwarder regression cases.

From the repository root, build into a complete disposable payload farm containing the unchanged baseline dependencies:

```sh
DEST=/absolute/path/to/staging/arm64ec-windows \
  bash build/wine-pe/build-modules.sh \
  rsaenh dssenh ncrypt wsock32 mswsock \
  msimg32 opengl32 glu32 wtsapi32 dwmapi \
  winhttp jsproxy dwrite schannel

python3 tools/check-wine-crypto-dlls.py /absolute/path/to/staging/arm64ec-windows \
  --root ncrypt.dll --root wsock32.dll --root msimg32.dll --root opengl32.dll \
  --root wtsapi32.dll --root dwmapi.dll --root winhttp.dll --root dwrite.dll \
  --root schannel.dll

PYTHONDONTWRITEBYTECODE=1 python3 tests/host/check-wine-media-dlls.py --fixtures-only
bash -n build/wine-pe/build-modules.sh
```

Validation completed:

- Baseline missing-provider farm rejected; i386 provider substitution rejected.
- Real ARM64EC CP exports and packaged dependency closure passed.
- Missing mswsock forwarder target rejected; completed forwarder closure and ordinal 1142 target passed.
- Final closure: 74 modules including specified roots. API-set handling checks the schema carrier's presence; it is not a full symbol-by-symbol API-set resolver.
- Existing malformed-PE/media fixture cases and new forwarder cases passed. The full pre-existing media test could not run against the main checkout's farm because its unrelated `mf.dll` is absent; fixture-only success is not represented as full media acceptance.
- App/helper IDs, build numbers, profile expiry/device registration, nested signatures, IPA CRC, hashes and allowed payload differences checked for every installed candidate.
- Wine/FEX worktrees are unchanged after temporary Makefile restoration. No FEX code contributions were made.

Local evidence includes each `buildNNN-artifacts/package-manifest.json`, device-cycle/private captures, static validation JSON, and `diagnostics/steam64-provider-fix-20261105/runtime-comparison.json`. The local `analyze-runs.py` recreates a categorical digest without copying arbitrary messages or credentials. The earlier REA plist Evidence remains metadata evidence; these runtime results came from CoreDevice captures and ordinary parsing, not REA decompilation/runtime Evidence.

## Next measurable experiment

The next change should address large-image placement, not add DLLs merely because optional probes mention them.

1. Preserve Build157 IPA, source/archives and a verified prefix backup before another allocator/client experiment.
2. Establish whether a large-image region-C route can safely satisfy a CEF image with the existing RX/RW alias, relocation, ownership ledger, branch reach, live-code and reuse-grace contracts. The current 16 MiB bound must not simply be removed without checking those contracts.
3. If viable, add a default-off, narrowly scoped large-image allocation experiment and log image size, selected region and owner categorically. Keep FEX, TLS, authentication and unrelated placement behavior fixed.
4. Require two concurrent/restarted CEF image loads without pool exhaustion, a visible login window, and cold-start repetition. If unsuccessful, restore the baseline and investigate image-copy duplication/fragmentation rather than reporting total free bytes as sufficient executable capacity.

Rollback can restore a preserved IPA using the same bundle ID; it does not undo Steam's on-device update. Reproducing the original Build152 condition requires an independently verified prefix snapshot as well. Login, Steam Guard, Big Picture and games remain unverified.

## Executed follow-up

See [Builds158–160 memory experiments](STEAM64_BUILDS158_160_MEMORY_2026-11-05.md) for signatures without either optional memory entitlement, the reproducible native-object patch, successful initial 211.81 MiB region-C placement, and the remaining FEX arena/restart failures. Initial placement is not login acceptance.
