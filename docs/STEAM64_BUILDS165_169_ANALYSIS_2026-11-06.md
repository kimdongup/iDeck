# Steam64 Builds 165–169 Analysis and Upstream Alpha.6 Integration

**Date:** 2026-11-06  
**Target Environment:** iPhone 15 Pro Max (`iPhone16,2`), iOS 18+, Free Developer Account (Zero paid entitlements, user space ceiling `TASK_VM_INFO.max_address = 0x7180000000` / 454 GB)  
**App Bundle ID:** `com.kimdongup.ideck.build149` (Update-install only, strictly preserving user container and prefix)  

---

## 1. Executive Summary

During testing of 64-bit Steam execution on physical hardware without paid entitlements, Steam completed its initial bootstrap update (following Build 153–157's addition of missing CryptoAPI provider DLLs `rsaenh.dll` and `dssenh.dll`). However, launching the 64-bit Steam web helper (`steamwebhelper.exe` + `libcef.dll`) encountered consecutive memory and execution barriers within the Free Developer Account's virtual address constraints.

Over Builds 165 through 169, each layer of the virtual memory and translation lifecycle was diagnosed, patched, and verified on-device. Concurrently, upstream released **iDeck v0.1.3-alpha.6 (Build 145)** on GitHub, introducing the 4-action launcher setup, verified manifest 1769025840 client acquisition, and source-built Chromium ELF compatibility components.

---

## 2. Detailed Technical Breakdown: Builds 165–169

### 2.1 Build 165: In-Memory Patching & Soft Pool VA Clamping
- **Observation:** Modifying PE binaries directly on disk breaks the Steam bootstrapper's SHA/CRC integrity checks, triggering automatic redownloads.
- **Fix:** Implemented Wine loader in-memory patching in `virtual_ios.c` for `chrome_elf.dll`'s `InitializeCrashReporting` (`0x7D014 -> ret 1`).
- **VA Constraint:** Clamped `ios_soft` pool base allocations strictly within `[0x7100000000, 0x7160000000)` to prevent collision with iOS furniture and stay below `0x7180000000`.
- **Result:** Bootstrapper CRC verified, soft pool allocated. However, `VirtualFree` returned `STATUS_MEMORY_NOT_ALLOCATED (0xc00000a0)` because unbacked soft pools lacked a Wine `file_view`.

### 2.2 Build 166: Intercepting VirtualFree for Soft Pools
- **Fix:** Added `ios_soft_release` in `NtFreeVirtualMemory` to intercept `MEM_RELEASE` calls on `ios_soft` address ranges.
- **Result:** Chromium's PartitionAlloc probe succeeded, and `libcef.dll` (200MB+) loaded successfully into memory.
- **New Failure:** Returning `*size_ptr = 16GB` on release triggered FEX's `[iOS-xrem]` invalidation tracker (`InvalidationTracker.cpp:500`), which purged JIT execution tracking for guest DLLs (`chrome_elf.dll`, `libcef.dll`) sharing that 16GB window. This led to `AV EXEC of 71595BED50` and stack overflow `C00000FD`.

### 2.3 Build 167: Suppressing FEX [iOS-xrem] for Soft Pools
- **Root Cause:** Soft pools contain unbacked Chromium PartitionAlloc data reserves, never guest code. FEX invalidating execution tracking for this range destroyed valid guest code translations.
- **Fix:** Modified `ios_soft_release` to return `*served = 0`. FEX's JIT tracking was preserved.
- **Result:** Soft pool 16GB probes passed 3 times consecutively with zero crashes.
- **Next Barrier:** Chromium proceeded to request an unhinted 32GB reserve (`VirtualAlloc(NULL, 0x7ffff0000, MEM_RESERVE, PAGE_NOACCESS)`). Wine returned `STATUS_NO_MEMORY (0xc0000017)` because `virtual_ios.c` only attempted soft pool placement when a hint was provided (`*ret != NULL`).

### 2.4 Builds 168 & 169: Unhinted Jumbo Soft Pool Fallback
- **Fix:** Extended `NtAllocateVirtualMemory` in `virtual_ios.c`: when kernel-pick allocation fails for unhinted reserves with `*size_ptr >= 0x400000000ULL` (16GB or 32GB), Wine grants an unbacked soft pool within `[0x7100000000, 0x7160000000)`.
- **Device Verification (PID 4585):**
  ```text
  [soft-pool] RELEASE soft 0x7100000000 (size=0x400000000, committed=0x0)
  [soft-pool] GRANTED unhinted soft 0x7100000000 (size=0x7ffff0000) — safe within limit 0x7180000000
  [soft-pool] RELEASE soft 0x7100000000 (size=0x7ffff0000, committed=0x0)
  [soft-pool] GRANTED soft 0x7100000000 (base returned 0x7100000000, size=0x400000000)
  [soft-pool] GRANTED soft 0x7110000000 (base returned 0x710fff0000, size=0x400010000)
  ```
- **Result:** The 32GB unhinted PartitionAlloc reserve was successfully granted without exceeding the 454GB user-space limit!

### 2.5 PID 4585 Exit Analysis: Breakpoint at RVA 0x47FBB
- Following successful PartitionAlloc allocation, `steamwebhelper.exe` initialized DLLs, but hit `STATUS_BREAKPOINT (0x80000003)`:
  ```text
  007c:err:module:call_tls_callbacks [tls-life] ml704 RUN callbacks module=0000007159540000 reason=0 count=6 first=000000715958E110
  007c:err:module:loader_init "chrome_elf.dll" failed to initialize, aborting
  007c:err:module:loader_init Initializing dlls for L"C:\Program Files (x86)\Steam\bin\cef\cef.win64\steamwebhelper.exe" failed, status 80000003
  ```
- **Root Cause:** Valve's upstream updated `chrome_elf.dll` executes TLS callbacks and PartitionAlloc / Crashpad initialization that invokes an immediate debug break when Crashpad pipes / Chromium structures are mismatched.

---

## 3. Upstream Release Analysis: v0.1.3-alpha.6 (Build 145)

Upstream's release addresses precisely this `chrome_elf.dll` / CEF Crashpad architecture:
1. **Four-Action Setup Launcher:**
   - Action 1: Install / Upgrade to Steam64 (streaming acquisition of official Valve HTTPS packages).
   - Action 2: Connect LocalDevVPN.
   - Action 3: Pair this device (on-device pairing via Madeira).
   - Action 4: Enable JIT.
2. **Pinned Compatibility Snapshot:**
   - Manifest 1769025840 (January 22, 2026), CEF 126.
   - Bootstrap updates are explicitly held (`-nobootstrapperupdate -skipinitialbootstrap`) to preserve component harmony.
3. **Source-Built Chromium ELF Compatibility Components:**
   - `chrome_elf.dll` (size: 1,666,560 bytes, SHA-256: `673584661cd0044b186e40286b3d57a099b45002d3fc50f334ae1d3d14bc7621`) compiled with:
     * `regular_pool_bytes = 1073741824` (1GB instead of 16GB/32GB)
     * `brp_pool_bytes = 1073741824` (1GB)
     * Complete upstream `crashpad_1995.patch` integration.
   - `crashpad_handler.exe` and `config_guard.exe` staged in `C:\iDeckCEF64Crashpad\`.
   - `crash_reporter.cfg` configured to use the local external handler.

---

## 4. Code Synchronization & Incorporation

The following upstream components have been merged and integrated into the project:
- `app/Madeira/Steam64ClientInstaller.swift`: Official package downloader and stream extractor with SHA256 integrity verification.
- `app/Madeira/Steam64Packages.json`: Manifest package inventory.
- `app/Madeira/Steam64Setup.swift`: Waterfall setup state machine and staging.
- `app/Madeira/SteamUIDiagnostics.h`: Diagnostic sampling control.
- `app/Madeira/SteamUIExperiment.swift`: Four-action waterfall UI and runtime gating.
- `app/Madeira/Steam64Compatibility/`: Staged `chrome_elf.dll`, `crashpad_handler.exe`, and `config_guard.exe`.
- Verification suites `check-ideck-waterfall.py`, `check-steam64-setup.py`, and `check-steam64-install.py` all executed and passed.
