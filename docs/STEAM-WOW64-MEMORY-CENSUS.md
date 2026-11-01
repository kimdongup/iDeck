# iDeck Steam WoW64 — Virtual Address Census v1

**Branch:** `fix/wow64-guest-window-availability` from `v0.1.3-alpha.4` / Build 99 (`006e05d`).

## Confirmed hardware failure

The iPhone 15 Pro Max Build 99 log showed `MADEIRA_WOW_PLACEHOLDERS=1` exported correctly, but **no placeholder was reserved** and 32-bit Steam failed at `guest-window-reserve`. Kernel-reported free VA at three refusals was 4970, 2614, 2612 MB. Native policy requires a 4096MB window plus 8192MB remain by default, i.e. at least 12288MB *total* free. This total is not a guarantee of a contiguous 4GB-aligned free range.

## Implemented

- `build/wow_va_probe.h`: common **read-only** kernel-region/hole scanner, reporting total free bytes, largest contiguous hole/base, first 4GB-aligned candidate and count within a candidate band, scanned region count, and whether the scan was complete. It does not call `mmap`, `mach_vm_map`, or `mprotect`.
- `app/Madeira/JITAllocator.c/.h`: `jit_wow_va_probe(stage)` reads `TASK_VM_INFO.max_address` and kernel regions, logs `[wow-va]` via the existing JIT logging callback.
- `app/Madeira/ContentView.swift`: enable `MADEIRA_WOW_VA_CENSUS=1` for Steam UI sessions only, with `madeira.cfg` opt-out. Capture `app-pre-jit`, `app-post-jit`, `app-pre-wineserver`, `app-pre-wine`. Clear Steam-specific flags for unrelated launches. Existing Steam-only placeholder opt-in preserved.
- `build/ntdll-unix/virtual_ios.c`: capture `virtual-init-pre-holds`, `virtual-init-post-holds`, `placeholder-preflight`, `virtual-init-post-placeholder`, and at most eight `child-before-reserve` snapshots. Candidate band is selected by **actual** `ios_wow_band` policy.
- `build/ntdll-unix/loader_ios.c`: capture `post-fex-arena` snapshot.
- `tests/host/check-wow-va-probe.py`: native compiled ASAN/UBSAN tests for fragmented (total free >= 12GB yet no 4GB slot), unaligned exact 4GB, aligned exact 4GB, trailing gaps, kernel query failure and regular band.
- Existing host WoW64 tests updated to compile the new read-only common scanner.
- `/shared/iDeckRuntimeLab/collect-steam-wow-diagnostics.sh`: reports the new `va_census_stages` in its safe summary without retaining raw Steam logs.

## Settings in Documents/madeira.cfg

```ini
env.MADEIRA_WOW_PLACEHOLDERS = 1
env.MADEIRA_WOW_VA_CENSUS = 1
```

To turn off the additional probe in the **newly compiled build**:

```ini
env.MADEIRA_WOW_VA_CENSUS = 0
```

The diagnostic is compiled code: **merely adding the flag to the currently installed Build 99 cannot generate `[wow-va]` entries**. It requires a new iOS build with the C/Swift changes. The original Build 99 accepts `MADEIRA_WOW_PLACEHOLDERS` but could not reserve a slot in the verified trial.

Example format (illustrative numbers only):

```
[wow-va] stage=app-pre-jit map_end=0xfc0000000 free_mb=... largest_mb=... largest_at=... band=[...,...) candidate=... aligned_slots=... regions=... complete=1
[wow-va] stage=virtual-init-post-holds ...
[wow-va] stage=placeholder-preflight ...
[wow-va] stage=post-fex-arena ...
[wow-va] stage=child-before-reserve ...
```

`candidate` is a **possible aligned empty region**, not proof a fixed `mach_vm_map` would succeed or that its guard is valid. `complete=0` means the scan did not reach the task map's end; do not interpret incomplete totals as an exact inventory.

## Decision gate after real device data

1. **No 4GB candidate at `app-pre-jit`**: a pre-JIT reservation cannot work; another memory strategy or platform entitlement is needed.
2. **Candidate pre-JIT but not at `virtual-init-pre-holds`**: JIT pool/early framework allocation displaced the slot. Design a one-slot, non-clobbering Mach reservation before that displacement, followed by a Wine registration/adoption protocol. Do **not** blindly `MAP_FIXED` over existing regions.
3. **Candidate survives until `placeholder-preflight` but no placeholder**: analyze the minimum free-VA gate (8192MB default margin) independently of kernel fixed-mapping rejection; consider reducing **other VA allocations**, not simply zeroing the safety margin.
4. **Placeholder reserved/adopted but Steam still fails**: move to the next Steam/CEF failure stage. Avoid guessing from UI appearance.

## Validation and limitations

Local Linux host tests: `check-wow-va-probe.py`, `check-steam-wow-placeholder.py`, `check-lazy-windows.py`, `check-small-va-band.py`, `check-launch-routing.py`, `check-cfg-early-docs.py`, `check-steam-ui-machines.py`.

**Not done:** Xcode compiler/linker build, new IPA signing, iPhone execution, and actual early external Mach reservation. The Docker/Linux environment lacks Apple SDK and Swift compiler, and the repository's compiled iOS runtime artifacts are not fully present. Do not assume these static/host tests prove on-device operation.

This patch is **observability only** with a Steam-only existing placeholder mode. It does not lower `MADEIRA_WOW_MIN_FREE_GB`, allocate a 4GB host mapping, overwrite an existing task region, or claim to fix Steam yet.

**Signing:** the Personal Team has verified `increased-memory-limit`, but cannot provision `extended-virtual-addressing`; the original `com.kuschqin.madeira.steamui` Bundle ID is unavailable to register on that team. A new IPA would require a unique owned app ID and properly provisioned JIT Helper; installing a new app ID cannot preserve previous app data automatically. The user has explicitly agreed to fresh installation.

## v2 — Experimental pre-JIT reservation and verified Wine adoption

**Added to the same working branch; default OFF.** This is a controlled engineering experiment, not a validated fix for Steam on the iPhone.

- `app/Madeira/JITAllocator.c/.h`: `jit_wow_early_hold_try()` scans the kernel's real VA map and, only when the `MADEIRA_WOW_EARLY_HOLD=1` opt-in is present, map size is at least 48GB, total free VA is at least 4GB+8GB, and an aligned 4GB candidate exists, attempts a **single 4GB+host-page PROT_NONE Mach VM mapping** using `VM_FLAGS_FIXED` **without** `VM_FLAGS_OVERWRITE`. A failed candidate is skipped; the function does not unmap existing regions or lower the free-VA gate. It publishes `madeira_wow_early_base` and `madeira_wow_early_length` only on success.
- `build/ntdll-unix/virtual_ios.c`: after Wine's `mmap_init()`, `ios_wow_import_app_early_hold()` checks exact 4GB alignment, host-page guard length, current Wine guest band, region existence and `VM_PROT_NONE`, and no prior WoW placeholder/window registry entries. It registers the app-held address as a normal Wine reserved area and as an unadopted WoW placeholder. **No remap or unmap occurs at import.** The normal 32-bit child adopts the placeholder using existing code, and the free-VA safety gate is not applied a second time to an already reserved window.
- `app/Madeira/ContentView.swift`: Steam-only `env.MADEIRA_WOW_EARLY_HOLD = 1` opt-in; call before `StikJITHelper.allocatePool`, with `app-after-early-hold` diagnostics; inactive for ordinary launches. The hold belongs to the Mach task; a full app process restart is required to reset a successful experiment.
- `tests/host/check-steam-early-hold.py`: compile/run **the production app-owned hold function** against a fake Mach mapper and assert opt-in gate, fixed non-overwrite flag, 4GB+guard, idempotence, free-VA margin, and refused kernel mapping fallback.
- `tests/host/check-lazy-windows.py`: compile/run **the production Wine guest-window logic** against fake mapped regions to verify import and adoption without any new mapping after the original free-VA margin drops below 12GB, as well as refusal of an accessible/writable preheld mapping.
- `collect-steam-wow-diagnostics.sh`: counts `early_held`, `early_imported`, `early_import_rejected` and `early_candidate_refused` in the privacy-preserving output.

### Testing on a newly built and signed iDeck app

Use a newly built app under a **unique owned Bundle ID**; the original `com.kuschqin.madeira.steamui` cannot be registered on the user's Personal Team. Sign the main app AND `JITHelper.appex` for that ID. Before testing, retain the following in `Documents/madeira.cfg`:

```ini
env.MADEIRA_WOW_PLACEHOLDERS = 1
env.MADEIRA_WOW_VA_CENSUS = 1
# First experiment must be disabled to establish the instrumentation baseline:
env.MADEIRA_WOW_EARLY_HOLD = 0
```

First verify the new build emits `[wow-va]` stage lines; collect its log. **Only if the pre-JIT census shows a qualifying candidate and adequate free space** should a second fresh-process session set `env.MADEIRA_WOW_EARLY_HOLD = 1`. After a successful app prehold, expect:

```
[wow-early] held B=... size_mb=4096 guard=... kr=0 (experimental; Wine must adopt)
[wow-early] imported pre-JIT 4GB+guard placeholder B=.....
[wow-window] adopted placeholder B=...
[Wine child] ... reserve=0x0
```

If the prehold logs `skipped`, `candidate refused` or Wine logs `import REJECTED`, do **not** infer success or lower `MADEIRA_WOW_MIN_FREE_GB`. Read the new `latest-summary.txt`, check whether `aligned_slots` is zero at `app-pre-jit`, then refine reservations with actual device evidence. Set `env.MADEIRA_WOW_EARLY_HOLD = 0` and fully restart the iDeck process to disable the experiment.

### Build and signing limitation

The remote `cokacremote3` session is Linux and cannot compile against Apple's SDK or produce a valid signed IPA; the checked-out repository is missing several generated native libraries (`libntdll_unix.a`, `libwineserver.a`, `libdxmt_combined.a`). C host tests and static Swift path assertions do **not** establish that the new app links or that iOS 27 accepts a 4GB fixed mapping. Do not substitute an unsigned test app into an existing production bundle.
