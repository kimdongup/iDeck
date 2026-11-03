# Build 122 Post-run: CEF delay-load failures after wevtapi staging

Date: 2026-11-02 (HST). Evidence: user-supplied Build122 collector excerpt in chat plus exact PE at /shared/iDeckRuntimeLab/diagnostics/build121-libcef/libcef.dll and built IPA /shared/iDeckRuntimeLab/build122-artifacts/Output/iDeck-WoW64-Build122-Debug.ipa.

## Verified observations

- Build122 IPA contains Wine i386 wevtapi.dll (98,304 bytes, SHA256 ba1b74b6b6d35572a53892dc46bf1cab94e59df5d66c3d182b18cddd02b75269) and it appears as Load module wevtapi.dll at 0x7967390000 in the device log.
- The same process has later NOTREACHED/INT3 at libcef RVA 0x4c36732, with peb=0x7900310000.
- Different depth-2 return RVAs occur at that common fatal hook in the current excerpt: 0x972b2ef, 0x972b4e2 and 0x972ab90. The earlier Build121 0x972b7f6 (wevtapi) is no longer the sole path.
- Exact libcef SHA256: b2dc73b55ca1d6a44a594e97b4ddd57bd19e79b2d09521faf2dfb83f51e2a94e.
- Independently disassembled stub instructions at each RVA: mov eax, IAT slot; push descriptor VA; call __delayLoadHelper2; return address.
- Read associated PE IMAGE_DELAYLOAD_DESCRIPTOR (RVA-based) for each call: names/functions below. All current candidate DLLs are absent from the Build122 IPA i386-windows directory.

| Stub return RVA | Delay-load DLL | Named imports | Built IPA state |
| --- | --- | --- | --- |
| 0x972b2ef | WTSAPI32.dll | WTSFreeMemory, WTSQuerySessionInformationW, WTSRegisterSessionNotification, WTSUnRegisterSessionNotification | missing |
| 0x972b4e2 | api-ms-win-power-base-l1-1-0.dll | CallNtPowerInformation, PowerDeterminePlatformRoleEx | API Set file absent; host powrprof.dll absent |
| 0x972ab90 | dxgi.dll | CreateDXGIFactory1 | missing |
| 0x972b7f6 (older) | wevtapi.dll | EvtClose, EvtCreateRenderContext, EvtNext, EvtQuery, EvtRender | present |

Wine's dlls/apisetschema/apisetschema.spec maps api-ms-win-power-base-l1-1-0 -> powrprof.dll. This is an API Set alias, not a request to invent a DLL under the API Set name.

## Next work (before claiming CEF success)

1. Prepare Build123 Wine i386 WTSAPI32.dll and powrprof.dll with PE machine/export validation, copying into i386-windows and verifying packaging/symlinks. They are real Wine modules with specs and source.
2. Resolve DXGI using project's intended DXMT i386 provider, not an arbitrary Wine wined3d replacement: investigate current absence of dxmt/build-pe-i386 and build prerequisites. DXGI must provide CreateDXGIFactory1, load its dependencies, and support a safe graphics fallback.
3. Verify that the API Set descriptor resolves to powrprof under current WoW64 loader semantics. Test whether LoadLibrary succeeds in the crashing helper, not just presence in IPA.
4. After one changed build, correlate pid/PEB, exact delay descriptor, module-load event, and NOTREACHED return RVA in the **same helper**. The common fatal hook RVA alone cannot distinguish missing modules.
5. Track Crashpad separately, then BrowserReady and visible UI.

## Reproducible offline check (no REA full decompile required)

python3 tools/dev-build101/analyze-cef-delay-stubs.py /shared/iDeckRuntimeLab/diagnostics/build121-libcef/libcef.dll --ipa /shared/iDeckRuntimeLab/build122-artifacts/Output/iDeck-WoW64-Build122-Debug.ipa 0x972b2ef 0x972b4e2 0x972ab90 0x972b7f6

No code changes to Chromium or INT3 handling are recommended at this stage. Do not assume a DXGI DLL built for a different engine can be substituted without validating imports/backend behavior.
