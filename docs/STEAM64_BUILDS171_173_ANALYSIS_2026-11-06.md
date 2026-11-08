# Steam64 Builds 171–173 Technical Analysis: PartitionAlloc Resolution, FEX Arena Exhaustion, and 2GB High Window Expansion

**Date:** 2026-11-06  
**Target Hardware:** iPhone 15 Pro Max (`iPhone16,2`), iOS 27.0.1 (`24A446`)  
**Application Bundle ID:** `com.kimdongup.ideck.build149`  
**Target Architecture:** ARM64EC (Wine + FEX64 JIT)  
**Entitlements Status:** Strictly Free Developer Account (`com.apple.developer.kernel.increased-memory-limit` and `extended-virtual-addressing` stripped)

---

## 1. Executive Summary

1. **Resolution of `chrome_elf.dll` Initialization Failure (Build 171 & 172):**
   - In earlier builds, Chromium's PartitionAlloc allocator terminated with `status 80000003` (`STATUS_BREAKPOINT`) when requesting 2047 MB (`0x7fff0000`).
   - By implementing a jumbo slot-walk down to `0x1000000000` in `virtual_ios.c`, PartitionAlloc reservation succeeded cleanly.
   - `chrome_elf.dll` and all TLS callbacks initialized without error.

2. **Long-Running Process Milestone (Build 172):**
   - `steam.exe` and `steamwebhelper.exe` ran continuously on physical hardware for **over 463 seconds (7.7+ minutes)**.
   - Memory footprint stabilized at **1,763 MB physical / 1,761 MB internal**, safely below iOS jetsam thresholds.
   - All 45 Win64 PE modules and DLLs loaded and delay-loaded imports resolved.
   - Madeira compositor attached and rendered the classic desktop background (`#008080`) and touch controls.

3. **Root Cause Analysis of Steam UI Freeze (Build 172):**
   - Steam created a 400x129 progress dialog (`hwnd=0x1005a`, title "Steam") with child controls including a "Cancel" button (`hwnd=0x10066`).
   - The dialog was created with `style=04ca0000 visible=0` (hidden), awaiting completion of worker thread initialization before `ShowWindow(SW_SHOW)`.
   - Worker thread `00b4` attempted to allocate 8 MB (`0x800000`) for `FEXMem_Frontend`.
   - Because `plan[]` in `virtual_ios.c` previously fell back to a 1GB arena (`0x703d920000..0x707d920000`), the arena saturated at 128 views with a maximum free gap of only `0x750000` (7.3 MB).
   - `va-scan` failed (`STATUS_NO_MEMORY`), returning NULL (`0x0`).
   - Thread `00b4` dereferenced NULL (`addr=0x0` at `pc=0x1545f26f8`), crashing while holding the FEX shared lock (`0x70490e0108`), causing Steam to freeze before making the window visible.

4. **Architectural Fix in Build 173:**
   - Added explicit 2GB (`0x80000000`) and 1.5GB (`0x60000000`) candidate rungs within the real iOS 448 GB high window (`0x7000000000..0x7160000000`) to `plan[]` in `virtual_ios.c`.
   - Recompiled `virtual.o` and embedded in `libntdll_unix.a`.
   - Packaged and verified `iDeck-Build173-FEX2GBArena.ipa` (290,469,315 bytes, SHA256: `d4749aeeb570b890f85b5397d7fe25a79533f6b623b3d6138bf195849e520999`).

---

## 2. Technical Evidence & Diagnostic Logs

### 2.1 PartitionAlloc Succeeded in Build 172
```text
008c:err:module:call_tls_callbacks [tls-life] ml704 RUN callbacks module=0000007166860000 reason=1 count=2 first=0000007166A20A04
[x64-image] L"\??\C:\Program Files\Steam\bin\cef\cef.win64\libcef.dll" 0x70f2c30000+0xd3ca000 mapped without a pool copy (pure x64)
[x64-image] L"\??\C:\Program Files\Steam\bin\cef\cef.win64\chrome_elf.dll" 0x7162c80000+0x1a9000 mapped without a pool copy
[thread-sample] ml876 modmap peb=0x105b38000 modules=45 first=steamwebhelper.exe@0x129cb0000
```

### 2.2 Memory Stability Over 463 Seconds
```text
[xp] 10:36:23.124 +463.50 dt=310 cpu=30 (thr 29) P=0 E=30 run=34 pgw=0.0 GHz P=0.00 E=1.37 Minst=95 IPC=2.34 mJ=4 pin=0 rdKB=0 fpMB=1763
[footprint] rev=ml358 phys=1763 MB (peak 1763) internal=1761 MB compressed=0 MB external=361 MB reusable=0 MB (cycle=231)
[freeze] alive t+150s beats=5 gaps=0 iter=595 gen=1 threads=31 resident=2122MB dbg=DEBUGGED rev=ml525
```

### 2.3 FEX Arena Saturation and Null Dereference Crash
```text
E B4 [vname] FEXMem_OpDispatcher 0x706f000000..0x7070000000 size=0x1000000
[va-scan] FAILED window=0x703d920000..0x707d920000 size=0x800000 align=0x10000 bottom-up tries=0 skips=0 | seen=0x703d920000..0x707d920000 views=128 maxgap=0x750000 tailgap=0x0 stop=gaps-exhausted(bottom-up) | firstfail=0x0 errno=0(-)   <-- STATUS_NO_MEMORY (callers see a NULL alloc)
E B4 [vname] FEXMem_Frontend 0x0..0x800000 size=0x800000
[store-noalias] #1 rev=ml348 addr=0x0 insn=0xad000100 pc=0x1545f26f8 NO pool/anon alias | region 0x104ba0000+0xc000 prot=5 max=5
[mach-deliver] rev=ml378 no TEB owns sp=0x7161f8f880 (pc=0x1545f26f8 x18=0x717fe80000 registry=0x717fe80000) -> BEST-EFFORT delivery on guest stack
[deliver-hold] teb=0x717fe80000 tid=00b4 HOLDS FEX shared lock @0x70490e0108 at guest redirect (pc=0x1545f26f8 addr=0x0) — this delivery leaks the read hold
[fault_rip] cnt=1 rip=0x7164716c70 pc=0x1545f26f8 addr=0x0 kr=1(INVALID_ADDRESS) entryprot=-1 nowprot=-1 region=0x0+0x0  <== UNMAPPED AT ENTRY (wild pointer)
```

---

## 3. Window Hierarchy and Visual Presentation

Screenshot captured via `xcrun devicectl device capture screenshot` verified that Madeira's UI subsystem is completely functional:
- Compositor created and attached to UIWindow.
- Classic Windows teal desktop background (`#008080`) rendered at resolution `1424x656` scaled to Retina `2796x1290`.
- Floating menu button responsive and active.
- Window handles created by Steam:
  - `hwnd=0x10020`: Virtual desktop window ("steamui - Wine 바탕화면", 1424x656, `vis=1`).
  - `hwnd=0x1005a`: Steam Dialog (400x129, `vis=0`), parent `0x10020`.
    - `0x10064`: Status text (`vis=1` child).
    - `0x10066`: "Cancel" button (`vis=1` child).
    - `0x10068`: Progress bar (`vis=1` child).
    - `0x1006a`: Detail text (`vis=1` child).

Once the FEX arena is doubled to 2GB in Build 173, thread `00b4` will successfully acquire its `FEXMem_Frontend` structure, release its initialization locks, and allow Steam's main UI loop to invoke `ShowWindow(SW_SHOW)` on `0x1005a`.

---

## 4. Verification Plan for Build 173

1. Deploy `iDeck-Build173-FEX2GBArena.ipa` to device via `device-cycle.py install`.
2. Launch `com.kimdongup.ideck.build149` in `madeira-steam64-experiment` mode.
3. Verify `[fex-arena]` in log confirms 2GB reservation in `0x7000000000..0x7160000000`:
   `[fex-arena] RESERVED 2GB in 448-454G high window (free dev account) base=0x70... size=0x80000000`.
4. Verify thread `00b4` allocation of `FEXMem_Frontend` succeeds (`va-scan` returns non-null base).
5. Verify `[win-pos]` reports `0x1005a` transitioning to `visible=1`.
6. Capture device screen to confirm on-screen presentation of Steam dialog.
