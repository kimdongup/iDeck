# Steam64 Runtime Analysis & Missing DLL Resolution

**Date:** 2026-11-06  
**Target:** iPhone 15 Pro Max (`iPhone16,2`), iOS 27.0.1 (`24A446`)  
**App Bundle:** `com.kimdongup.ideck.build149` (Build 171)  
**Profile:** Free Developer Account (No `com.apple.developer.kernel.increased-memory-limit`, No `extended-virtual-addressing`)  

---

## 1. Summary of Milestones Achieved

1. **`steamui.dll` Load Failure Resolved (`c0000135`):**
   - Wine loader missing-module diagnostics (`steam64.env.MADEIRA_STEAM_UI_MODULE_ERRORS = 1`) pinpointed missing ARM64EC DLLs: `ncrypt.dll` and `wsock32.dll`.
   - Missing these caused `libavformat-62.dll` and `video64.dll` to fail, which cascaded to `steamui.dll` failing to load with `c0000135` (`STATUS_DLL_NOT_FOUND`).
   - Staging `ncrypt.dll`, `wsock32.dll`, `mswsock.dll`, `rsaenh.dll`, and `dssenh.dll` into `system32` and `Program Files/Steam` completely solved `steamui.dll` loading.

2. **Valve UI (`vgui2_s.dll`) Load Failure Resolved:**
   - `vgui2_s.dll` was failing with missing dependency errors for:
     - `msimg32.dll`
     - `opengl32.dll`
     - `wtsapi32.dll`
     - `dwmapi.dll`
   - In addition, delay-loaded Chromium/CEF modules were missing:
     - `uxtheme.dll`
     - `actxprxy.dll`
     - `kerberos.dll`
     - `msv1_0.dll`
     - `xinput1_4.dll`
     - `dwrite.dll`, `glu32.dll`, `jsproxy.dll`, `schannel.dll`, `winhttp.dll`
   - Extracted all corresponding ARM64EC and x86_64 DLLs from the built toolchains and staged them into `drive_c/Program Files/Steam/`, `drive_c/windows/system32/`, and `drive_c/windows/sysx64/`.
   - `vgui2_s.dll` loaded successfully!

3. **CEF / `steamwebhelper.exe` Spawn & Execution:**
   - With the full DLL suite in place, Wine successfully spawned `steamwebhelper.exe` (PID 008c).
   - `libcef.dll` (at `0x70F2C30000`), `steamclient64.dll` (at `0x71638E0000`), `chrome_elf.dll`, `DWrite.dll`, and `tier0_s64.dll` were all mapped and initialized without missing-DLL errors!

4. **Breakthrough Diagnosis of `steamwebhelper` Exit (`status 80000003`):**
   - During `chrome_elf.dll` initialization, Chromium's PartitionAlloc requested a 2047 MB (`0x7fff0000`) jumbo memory reservation via `VirtualAlloc`.
   - On a Free Developer Account, the iOS task ceiling is strictly clamped at `0x7180000000` (due to the absence of `extended-virtual-addressing`).
   - The 2 GB allocation failed with `c0000017` (`STATUS_NO_MEMORY`).
   - `chrome_elf.dll` asserts on allocation failure (`0f 0b` / `UD2`), raising `STATUS_BREAKPOINT` (`0x80000003`) and terminating the CEF helper process.

---

## 2. "Install Steam64" UI Inactivity Root Cause

- In `SteamUIExperiment.swift`, the environment management button (`canManageEnvironment`) contains a strict guard:
  ```swift
  var canManageEnvironment: Bool {
      wine_process_is_running() == 0 && wineserver_is_running() == 0
  }
  ```
- When an earlier Wine process, `wineserver`, or stale helper (e.g. PID 4895, 4896, 4988, 4991) remained active in the background, `canManageEnvironment` remained `false`.
- Consequently, taps on "Install Steam64" were ignored with no user feedback.
- **Resolution:**
  - Ensure background Wine processes are terminated via `xcrun devicectl device process terminate --kill`.
  - Adopt the `IDeckSetupFlow` four-action waterfall from `v0.1.3-alpha.6` which provides visible progress indicators and decoupled status checks.

---

## 3. GitHub Release `v0.1.3-alpha.6` Upstream Comparison

The upstream release `v0.1.3-alpha.6` (commit `2ac39be` / `050b592` / `6422597`) introduced:
1. **Four Direct Actions Waterfall (`IDeckSetupFlow`):**
   - Step 1: Install Steam (verifies 18 Valve packages & 6229 file hashes).
   - Step 2: Connect LocalDevVPN (StikJIT loopback).
   - Step 3: Pair this device.
   - Step 4: Enable JIT -> Launch Steam.
2. **Crashpad Config Guard Integration:**
   - Pre-launch execution of `config_guard.exe --restore` and `--protect` to prevent CEF crash loops.
3. **Suppression of Background Guest Log List:**
   - In `ContentView.swift`, toggles `logStore.setDisplayActive(!running)` so SwiftUI doesn't freeze or drop frames rendering raw debug strings during Steam execution.

---

## 4. Xcode Device Support Cache Guidance

Regarding `/Users/kimdongup/Library/Developer/Xcode/iOS DeviceSupport/iPhone16,2 27.0.1 (24A446)`:
- **Yes, it can be safely deleted.**
- It contains symbol files (`dyld_shared_cache` symbols) extracted by Xcode for symbolicating crash logs.
- Xcode will automatically re-extract symbols when needed if a debugger is attached.
- Deleting it will reclaim several gigabytes of disk space without affecting device operation.
