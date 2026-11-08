# Build163: Dead Pseudo-Process FEX Arena Reclamation and CEF Process Suppression

2026-11-05 HST. Follow-up to [Build162](STEAM64_BUILD162_CALLRET_FIX_2026-11-05.md).

## Problem Analysis from Build162

In Build162, arena fragmentation was reduced to near-zero ( 가용 공간 점유율 99.12% ), but execution stalled at line 46,466 when 16 MiB allocations exhausted the 2 GiB FEX arena.
Analysis revealed:
1. **Accumulation of Dead Process Memory:**
   - Steam spawned multiple CEF sub-processes (`steamwebhelper.exe`) consecutively.
   - In Wine on iOS (Madeira), all pseudo-processes run within a single Darwin Mach task.
   - When a pseudo-process terminated, Wine's `process_exit_wrapper` reclaimed its 32-bit WoW64 window, JIT pool mappings, and fixed-base image, but **did not reclaim any generic or FEX arena views**.
   - As a result, 16 MiB `rpmalloc` spans and supporting buffers from exited sub-processes remained registered in Wine's `views_tree` and `reserved_areas` indefinitely.
2. **Sub-process & Thread Explosion:**
   - Chromium/CEF defaults to multi-process architecture (browser process, renderer processes, GPU process, utility processes), multiplying FEX initialization and memory demands across multiple instances.

## Build163 Changes

To resolve these issues without requiring paid developer entitlements, two coordinated solutions were implemented:

### 1. Process-Tagged FEX Arena View Reclamation (`virtual_ios.c`)
- **View Ownership Tagging:**
  - Added `void *owner_peb;` to `struct file_view`.
  - In `create_view()`, automatically tagged newly allocated views with the allocating pseudo-process's PEB:
    `view->owner_peb = ios_jit_current_peb();`
  - In `free_pages()`, propagated `owner_peb` to split child views (`new_view->owner_peb = view->owner_peb;`).
- **Forced FEX Arena View Teardown on Process Exit:**
  - Implemented `ios_fex_reclaim_process( void *dead_peb )`:
    Scans `views_tree` within `[ios_fex_arena_base_unix, ios_fex_arena_end_unix)` under `virtual_mutex`.
    Batches views matching `view->owner_peb == dead_peb` and deletes them via `delete_view(view)`.
    Calls `unmap_area()` to reset pages to `PROT_NONE, MAP_NORESERVE` and `unregister_view()` to return contiguous ranges to `free_ranges`.
  - Hooked `ios_fex_reclaim_process()` into `ios_jit_reclaim_process()` at process termination.

### 2. CEF Multi-Process & Thread Explosion Suppression
- Injected strict Chromium/CEF single-process and resource-limiting parameters:
  `--renderer-process-limit=1 --single-process --in-process-gpu --disable-gpu --disable-gpu-compositing`
- Configured in:
  - Runtime environment via `MADEIRA_CHILD_ARGS` in `device-cycle.py`.
  - Batch scripts in `SteamUIExperiment.swift` (L93) and `ContentView.swift` (L3713).

---

## Package Conditions

- Base IPA: `build162-artifacts/iDeck-Build162-FEXCallRetFix.ipa`.
- Modified units:
  - `virtual_ios.c` recompiled via `compile-virtual.py` into `virtual.o`.
  - `libntdll_unix.a` archive updated and relinked via `relink.py` into `Madeira.debug.dylib`.
- Source trees updated:
  - `iDeck/build/ntdll-unix/virtual_ios.c`
  - `iDeck/app/Madeira/SteamUIExperiment.swift`
  - `iDeck/app/Madeira/ContentView.swift`
- Entitlements:
  - Strictly compliant with free Apple developer accounts.
  - `com.apple.developer.kernel.increased-memory-limit`: **Removed**.
  - `com.apple.developer.kernel.extended-virtual-addressing`: **Removed**.
- Bundle ID: `com.kimdongup.ideck.build149`, `CFBundleVersion = 163`.
- Package hash: `candidate_sha256 = 16d90fcf85c21105522c8bf54c4d03b1380ba6cfee80780395a3cad51dc6c15a`.

---

## Hardware Test Results

Executed on iPhone 15 Pro Max (iOS 27.0.1, Xcode 27.2) on 2026-11-06 00:04:05 HST (`capture-20261106-000405`).

### 1. FEX Arena View Reclamation Verified
The on-device log confirmed two successful reclamation cycles when CEF sub-processes exited:
- **Cycle 1 (Line 44,804):**
  `[fex-reclaim] RECLAIM peb=0x101f70000: freed 16 FEX arena views (0x5232000 bytes / 82 MiB)`
- **Cycle 2 (Line 52,582):**
  `[fex-reclaim] RECLAIM peb=0x1011d8000: freed 16 FEX arena views (0x5232000 bytes / 82 MiB)`
- **Total Reclaimed:** **32 views, 164 MiB** restored to the FEX arena's `free_ranges` for subsequent allocations.

### 2. Elimination of Memory Exhaustion Errors
- **`STATUS_NO_MEMORY`:** **0 instances** (previously 5+ instances in Build 162).
- **`C0000017` (Out of Memory):** **0 instances**.
- **`FEX Arena Census` Failure Dump:** **Did not trigger** (no allocations failed).
- **Advisory VA Scan Retries:** All 4 scan fails in Build 163 were non-fatal ceiling checks that safely relaxed and succeeded (`--> relaxing ceiling, retrying unclamped`).

### 3. Stability and Runtime Continuity
- **Execution Longevity:** Log progressed to **52,657 lines** (up from 46,466 lines in Build 162, a gain of +6,191 lines).
- **Process Health:**
  - Steam client survived and remained active at t+38.5 seconds.
  - Window creation successful: `[winios-tree] 0x40030 '' "" style=04c80000 win={0,0,166,52}`.
  - Physical memory footprint stabilized at **3,191 MB** (peak **3,197 MB**), safely below OS jetsam limits.
  - CPU utilization settled to **32%~48%** across background threads.
