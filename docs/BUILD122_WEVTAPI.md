# Build 122 — Wine i386 wevtapi.dll for Steam CEF delayed load

## Root-cause evidence
- Device: iPhone 15 Pro Max, Build 121, two repeated steamwebhelper crashes with guest INT3 at 0x6e0e6732 and post-int3 RIP 0x6e0e6733.
- libcef.dll: SHA-256 b2dc73b55ca1d6a44a594e97b4ddd57bd19e79b2d09521faf2dfb83f51e2a94e, RVA 0x4c36732 in the cited Steam32BundleLab version.
- Reported REA disassembly: System event log query through EvtQuery; delay-load helper attempts wevtapi.dll. Missing DLL triggers Chromium NOTREACHED hook instead of handled NULL-return path.
- Wine original dlls/wevtapi/main.c already implements EvtQuery as a NULL-returning stub.
- Existing app/Madeira/i386-windows has no wevtapi.dll in Build 121.

## Scope
- Build authentic Wine wevtapi.dll for PE32 i386 using existing pinned bootstrap build tree.
- Validate Machine=0x014c, PE32, and exports EvtQuery, EvtNext, EvtRender, EvtClose, EvtCreateRenderContext.
- Stage unchanged compiled DLL at app/Madeira/i386-windows/wevtapi.dll; Xcode packages i386-windows as folder resource.
- Existing WineProcessBridge.m creates/refreshes syswow64 symlinks from packaged i386-windows every session.
- Make full build/wine-i386/build.sh refuse to omit delay-load wevtapi.
- No libcef patch, Wine stub modification, exception suppression, Crashpad policy change, or FEX policy changes.

## Build on Mac
```bash
bash /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck/tools/dev-build101/build122-on-mac.sh --build
```

## Install and launch
```bash
bash /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck/tools/dev-build101/build122-install-launch-on-mac.sh "00008130-000451D91A31001C"
```

## Collect
```bash
python3 /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck/tools/dev-build101/build107-collect-logs-on-mac.py --device "00008130-000451D91A31001C"
LOG=$(ls -dt ~/Downloads/ideck-build107-device-* | head -1)
grep -nEi 'wevtapi|EvtQuery|delay.?load|NOTREACHED|check.cc|build121-libcef|steam-ui-remote-exception32|crash server did not respond|browser.ready|event=end kind=cef' "$LOG"/madeira-log*.txt | tail -100
```

## Acceptance
1. Build: staged DLL and IPA are valid i386 PE; five required exports verified. In-use source and app copy match.
2. Runtime: i386 wevtapi.dll really loads in the affected steamwebhelper; optional Wine FIXME may identify EvtQuery stub.
3. Behavior: former NOTREACHED at RVA 0x4c36732 no longer repeats; if new failure appears, characterize the next *missing DLL* without bypassing the hook.
4. End goal: BrowserReady plus visible Steam interface and repeated-launch stability. Loading wevtapi is **not** sufficient to claim CEF fully works.
5. Only Build 122 output accepted as a successful build when xcodebuild + IPA gates pass. Linux source/bash checks do not imply a Mac build or iPhone run.

## Environment notes
- The Mac-specific Wine i386 build tree under wine/build-i386 is not present in the shared Linux environment; Build 122 explicitly uses the existing configured wine/build-bootstrap-pe, which does have an i386 wevtapi target.
- Submodule worktrees FEX and wine have pre-existing local modifications and are deliberately left untouched.
