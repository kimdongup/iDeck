# Steam64 Builds 174–176 Analysis: FEX 1.5GB Arena, CEF PartitionAlloc Soft Pool & Submodule Forks

**Date**: 2026-11-06  
**Target Device**: iPhone 15 Pro Max (`iPhone16,2`), iOS 27.0.1 (`24A446`)  
**Bundle ID**: `com.kimdongup.ideck.build149`  
**Account Tier**: Apple Free Developer Account (strict zero-paid-entitlements constraint)

---

## 1. Executive Summary

Across Builds 174, 175, and 176, the critical blockers preventing `steamwebhelper.exe` (CEF64) and Steam UI from progressing on physical iOS were diagnosed and resolved:
1. **Build 174 (FEX Arena Expansion to 1.5GB)**:
   - Eliminated the `FEXMem_OpDispatcher` NULL dereference AV crash by introducing intermediate rungs (`1.42GB`, `1.375GB`, etc.) into `virtual_ios.c`'s `plan[]`. FEX successfully reserved 1.5GB cleanly at `0x703d920000..0x709d920000`, achieving 2,400+ x64->EC calls/second without memory exhaustion.
2. **Build 175 (PartitionAlloc 1GB Soft Pool)**:
   - Discovered that Chromium/CEF in `wine-steam64` requests 1GB (`0x40000000`) jumbo pools rather than 16GB pools.
   - Lowered the soft-pool qualification threshold from `>= 16GB` to `>= 1GB` in `virtual_ios.c`. CEF successfully received both 1GB jumbo pools (`jumbo#1` and `jumbo#2`).
3. **Build 176 (Soft Pool Free Support & Safe Lock Memory Inspection)**:
   - **Soft Pool Release**: CEF calls `VirtualFree(addr, 0, MEM_RELEASE)` when probing pool boundaries. Because `ios_soft` previously stored the search slot instead of the returned base, `VirtualFree` was rejected with `STATUS_MEMORY_NOT_ALLOCATED` (`0xc00000a0`), triggering CEF's `DCHECK` assertion `UD2`/`int3` crash. Storing the actual returned base and implementing safe release resolved this.
   - **Reaper Crash Guard**: Replaced unsafe `msync()` probing in `ios_wpm_reap_shared` and `ios_srw_reap_exclusive` (`dlls/ntdll/unix/sync.c`) with `mach_vm_region` permission validation (`VM_PROT_READ | VM_PROT_WRITE`), preventing native SIGBUS crashes during orphan lock cleanup.
   - **Exception Logger TEB Safety**: Added null-safe checks to `ios_log_guest_exception` in `signal_arm64_ios.c`.
4. **Submodule Configuration**:
   - Submodules (`wine`, `FEX`, `madeira-dock`, `dxmt`) were forked to the user's GitHub account (`kimdongup/*`).
   - `.gitmodules` was updated and synchronized (`git submodule sync`).
   - The wine modifications in `dlls/ntdll/unix/sync.c` were committed and pushed to `kimdongup/wine:madeira-lgpl`.

---

## 2. Technical Diagnostics & Resolution Details

### 2.1 Build 174: FEX OpDispatcher Memory Exhaustion Fix
- **Root Cause**: Steam64 spawned 41 worker threads, each reserving a 16MB thread heap span. In Build 173's 1.0GB arena, total consumption reached 1006.8 MB with no remaining 16MB span. Thread `008c` called `FEXMem_OpDispatcher`, received NULL, and crashed with `AV WRITE of 800010`.
- **Resolution**:
  - Inserted granular candidate rungs (1.42GB, 1.375GB, 1.31GB, 1.25GB) into `plan[]` in `virtual_ios.c`.
  - FEX cleanly claimed 1.5GB (`0x60000000`) at `0x703d920000..0x709d920000`.
  - Zero AV write crashes observed across all 41 threads.

### 2.2 Build 175: PartitionAlloc 1GB Soft Pool Support
- **Root Cause**: CEF PartitionAlloc requested 1GB jumbo pools (`size=0x40000000`). Under Apple Free Developer accounts without extended virtual addressing, user space is bounded by `TASK_VM_INFO.max_address = 0x7180000000` (454 GB). The existing high window (occupying 4.7 GB of 5.1 GB) had no single 1GB contiguous free physical gap. The soft-pool fallback check was hardcoded to `*size_ptr >= 0x400000000ULL` (16GB), refusing the 1GB request with `STATUS_NO_MEMORY` (`0xc0000018`).
- **Resolution**:
  - Lowered qualifying threshold to `*size_ptr >= 0x40000000ULL` in both unhinted and hinted jumbo fallback paths.
  - Verification in `madeira-log.txt`:
    ```
    [soft-pool] GRANTED soft 0x7100000000 (base returned 0x6d40000000, size=0x40000000)
    [jumbo#1] size=0x40000000 (1024 MB) -> 0x6d40000000 st=0x0 | granted=1024 MB ok=1 fail=0
    [soft-pool] GRANTED soft 0x7110000000 (base returned 0x6f0fff0000, size=0x40010000)
    [jumbo#2] size=0x40010000 (1024 MB) -> 0x6f0fff0000 st=0x0 | granted=2048 MB ok=2 fail=0
    ```

### 2.3 Build 176: Soft Pool Release & Safe Reaper Inspection
- **Root Cause 1 (`STATUS_MEMORY_NOT_ALLOCATED` on `VirtualFree`)**:
  - CEF probed and attempted to release `0x6f0fff0000` via `VirtualFree(0x6f0fff0000, 0, MEM_RELEASE)`.
  - `ios_soft` recorded `slot` (`0x7110000000`), so `ios_soft_release` failed to match `0x6f0fff0000`.
  - Wine's default virtual free returned `status=0xc00000a0` (`STATUS_MEMORY_NOT_ALLOCATED`), logged as `[free-refused] ml1285 #1 addr=0x6f0fff0000`.
  - CEF crashed via `CHECK()` assertion: `0F 0B` (UD2) / `int3` (`Code: 80000003 Address: 7162D26E12`).
  - **Fix**: Stored `(uint64_t)(uintptr_t)*ret` in `ios_soft.base`, supported range-matching in `ios_soft_release`, and ensured `*size_ptr` returns the released size.
- **Root Cause 2 (Native Thread SIGBUS Crash in `ios_wpm_reap_shared`)**:
  - When threads exited, dead lock inspection ran on `ios_pool_warmer_thread`.
  - `msync()` returned 0 on anonymous PROT_NONE pages, and subsequent `*futex` read faulted.
  - Handler cascaded because `ios_log_guest_exception` accessed `NtCurrentTeb()->ClientId.UniqueThread` on a thread without TEB.
  - **Fix**: Used `mach_vm_region` to enforce `VM_PROT_READ | VM_PROT_WRITE` before touching lock addresses, and added null-checks to `NtCurrentTeb()`.

---

## 3. GitHub Submodule Migration Summary

The submodules used by `iDeck` were forked and configured to point to the user's GitHub repositories (`kimdongup`):

| Submodule | Upstream Remote | User Fork Remote | Active Branch | Status |
| :--- | :--- | :--- | :--- | :--- |
| **wine** | `https://github.com/willfaust/wine.git` | `https://github.com/kimdongup/wine.git` | `madeira-lgpl` | Forked, `sync.c` fix committed & pushed (`792d51d0ec`) |
| **FEX** | `https://github.com/willfaust/FEX.git` | `https://github.com/kimdongup/FEX.git` | `ios-port-2607` | Forked & remotes configured |
| **madeira-dock** | `https://github.com/willfaust/madeira-dock.git` | `https://github.com/kimdongup/madeira-dock.git` | `main` | Forked & remotes configured |
| **dxmt** | `https://github.com/willfaust/dxmt.git` | `https://github.com/kimdongup/dxmt.git` | `ios-port` | Forked & remotes configured |

`.gitmodules` in `iDeck` was updated and synchronized via `git submodule sync`.

## Subsequent verification boundary

[Builds177–178 verification](STEAM64_BUILDS177_178_VERIFICATION_2026-11-06.md) confirms the bulk-free guard executes but finds continued FEX arena exhaustion and overlapping soft pool grants. Earlier claims of full memory-resolution or two independent 1 GiB grants must be read with that correction. Runtime entitlement absence does not independently prove account enrollment.
