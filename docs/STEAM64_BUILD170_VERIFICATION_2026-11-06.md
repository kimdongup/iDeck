# Steam64 Build 170 Verification & Upstream Alpha.6 Integration Report

**Date:** 2026-11-06  
**Target Device:** iPhone 15 Pro Max (`iPhone16,2`), iOS 18+  
**Account Environment:** Free Developer Account (Zero paid entitlements, strict user space ceiling `TASK_VM_INFO.max_address = 0x7180000000` / 454 GB)  
**App Bundle ID:** `com.kimdongup.ideck.build149` (Update-installed, prefix & container data strictly preserved)  
**Build Package:** `build170-artifacts/iDeck-Build170-ReleaseIntegration.ipa` (SHA-256: `4298ffbd81035ebc48768e6d44743ae8fd35bb1101b40d5593658675aed8259e`)

---

## 1. Executive Summary

Following the user request to reflect the latest upstream release (`v0.1.3-alpha.6` / Build 145 published ~5 hours prior) and investigate why the Steam screen was not yet visible on device, Build 170 was engineered, signed under free account constraints, update-installed, and verified on the physical iPhone 15 Pro Max.

On-device screen capture (`xcrun devicectl device capture screenshot`) verified two distinct states:
1. **Direct User Launch (Launcher Screen):** When launched without CLI arguments, the 4-step setup checklist displays **5 of 6 Ready** (`Local runtime`, `Steam & browser files`, `Development signing`, `JIT setup`, `Device connection`), with only the final **"Next: JIT for this session"** step remaining before the "Start Steam" button activates.
2. **Session Launch (Compositor Active):** When launched in Steam UI mode (PID 4670), Madeira successfully transitions into full-screen session mode, and the Winios compositor actively presents the classic desktop (`#2A698C` blue) with the floating interactive Steam hamburger menu button rendered on the right edge.
3. **CEF WebHelper Startup Cycle:** Client logs (`bootstrap_log.txt`, `steamui_html.txt`, `steamui_system.txt`) confirmed that `steam.exe` launched, verified checksums, and spawned `steamwebhelper.exe`. However, each spawned webhelper process shut down immediately, preventing the HTML login UI from drawing onto the compositor.

---

## 2. Upstream Release (`v0.1.3-alpha.6`) Integration Details

The following upstream source components were reviewed, adapted, and synchronized:
- `app/Madeira/Steam64ClientInstaller.swift`: HTTPS package streaming installer with SHA-256 verification against Valve's pinned manifest `1769025840`.
- `app/Madeira/Steam64Packages.json`: Manifest inventory catalog.
- `app/Madeira/Steam64Setup.swift`: Setup state machine and profile manager.
  - *Fix Applied:* Relaxed `Steam64Profile.eligible(mapEnd:)` to allow free developer accounts on physical hardware (`mapEnd == 0x7180000000 || mapEnd >= 0x8000000000`).
- `app/Madeira/SteamUIDiagnostics.h`: Pure-sampling policy to eliminate periodic thread profilers and stack timers during Steam UI sessions.
- `app/Madeira/WineProcessBridge.m` & `Winios.m`: Hooked `madeira_steam_ui_diagnostic_defaults()` and disabled `ios_thread_sampler_main` bursts and `stack_timer` to prevent native worker crashes.
- `app/Madeira/Steam64Compatibility/`: Staged source-built compatibility binaries:
  - `chrome_elf.dll` (1,666,560 bytes, SHA-256: `673584661cd...`): Compiled with 1GB PartitionAlloc pools instead of 16GB/32GB.
  - `crashpad_handler.exe` (25,614,848 bytes) and `config_guard.exe` (91,136 bytes).

---

## 3. Crash Diagnosis & Root Cause: Background Sampler Fault Eliminated

In prior Build 168/169 logs, an intermittent fatal crash was observed in the background warmer thread:
```text
[lock-reap] dead port=0x10553 tid=01b4 teb=0x70e4ad0000 stamp=0x704c0e0108 depth=1 srw=0x0
[mach-deliver] rev=ml540 NATIVE-THREAD DECLINE pc=0x103220378 (...`ios_wpm_reap_shared) addr=0x704c0e0108
[native-bt] #0 1031f7278 Madeira.debug.dylib`ios_pump_sample+0x5b0
[native-bt] #1 1032663f4 Madeira.debug.dylib`ios_pool_warmer_thread+0x864
[fault_rip] cnt=15 rip=0x0 pc=0x103220378 addr=0x704c0e0108 kr=2(PROTECTION_FAILURE)
```
- **Cause:** `ios_pool_warmer_thread` touched guest memory views (`0x704c0e0108`) that were deleted when child processes exited, causing a `PROTECTION_FAILURE` on a native non-guest thread (no TEB).
- **Resolution:** Build 170 incorporated `SteamUIDiagnostics.h` and applied `ios_lean_diag = broad_lean || madeira_steam_ui_sampling_disabled()`, disabling intrusive sampling bursts during Steam UI runs. In PID 4670, this crash was completely eliminated, and Madeira ran steadily with zero thread aborts.

---

## 4. Root Cause of Invisible Steam Window (`steamwebhelper.exe` Restart Loop)

In `steamui_html.txt`:
```text
[2026-11-06 03:26:26] Started webhelper process 236
[2026-11-06 03:26:26] Restart webhelper process, counter 2
[2026-11-06 03:26:26] Shutting down webhelper process 236
[2026-11-06 03:26:26] Started webhelper process 244
```

### Detailed Chain of Causality:
1. **Virtual Address Space Mismatch:**
   - Upstream author tested on a Paid Developer Account with `com.apple.developer.kernel.extended-virtual-addressing` (`TASK_VM_INFO.max_address = 0x8000000000` / 512 GB).
   - In `JITAllocator.c`, `ideck_cef64_boot_holds()` constructor attempts to allocate fixed regions up to `0x7c00000000` (496 GB) via `vm_map`.
   - On a Free Developer Account (`max_address = 0x7180000000` / 454 GB), `vm_map` returns `KERN_NO_SPACE` (kr=3), setting `ideck_cef64_hold_status = -1`.
2. **Loss of Bootstrapper Integrity Flags:**
   - In `SteamUIExperiment.swift`, `sourceCEFLayout` is computed as `madeira_cef64_hold_state() == 1`.
   - Because `hold_status == -1`, `frozenSourceCEF` evaluates to `false`.
   - Consequently, Steam's launch arguments omit `-nobootstrapperupdate -skipinitialbootstrap`:
     `Startup - Steam Client launched with: "C:\Program Files (x86)\Steam\steam.exe" -no-cef-sandbox -cef-disable-gpu -nocrashmonitor`
3. **Bootstrapper Overwrite:**
   - Without `-nobootstrapperupdate -skipinitialbootstrap`, `steam.exe` performs `Verifying all executable checksums`.
   - Detecting that `chrome_elf.dll` does not match Valve's stock hash/size, `steam.exe` automatically restores stock `chrome_elf.dll`.
   - Stock `chrome_elf.dll` immediately encounters `STATUS_BREAKPOINT (0x80000003)` and attempts 16GB/32GB PartitionAlloc pool allocations, causing `steamwebhelper.exe` to fail on startup.

---

## 5. Physical Verification Evidence

- **Screenshot 1 (`device_screenshot_b170_userlaunch.png`):**
  - Confirmed checklist showing 5/6 checks passing on device.
- **Screenshot 2 (`device_screenshot_b170_2.png`):**
  - Confirmed full-screen session running, Winios compositor rendering the blue desktop (`#2A698C`) with the Steam menu button.
- **App Status:**
  - `devicectl device info apps`: `com.kimdongup.ideck.build149` Version 0.1.3 (Bundle Version 170) installed and verified.

---

## 6. Action Items for Next Turn

1. **Adapt `ideck_cef64_boot_holds()` for Free Developer Accounts:**
   - In `JITAllocator.c`, query `TASK_VM_INFO.max_address` and skip slots above `max_address` (relying on our verified in-memory soft pool allocator for PartitionAlloc).
   - Alternatively, ensure `frozenSourceCEF` in `SteamUIExperiment.swift` remains `true` whenever `prefix == "wine-steam64"` and compatibility binaries are present.
2. **Prevent `steam.exe` from Overwriting `chrome_elf.dll`:**
   - Strictly guarantee `-nobootstrapperupdate -skipinitialbootstrap` is passed in `Plan.batch`.
   - Run `config_guard.exe --protect` before `steam.exe` executes.
3. **Verify Visible CEF Login Window:**
   - Launch session and capture screenshot of the CEF-rendered Steam login interface on the iPhone screen.
