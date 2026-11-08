# Build162: FEX CallRetStack Top-Down Segregation and 64KiB Alignment

2026-11-05 HST. Follow-up to [Build161](STEAM64_BUILD161_FEX_LAYOUT_2026-11-05.md).

## Problem analysis from Build161

Build161 introduced `MADEIRA_FEX_SMALL_TOPDOWN=1` to pack small allocations from the
high end of the 2 GiB FEX arena. However, on-device analysis revealed that:
1. `FEXMem_CallRetStacks` requests `0x802000` bytes (8.0078 MiB: 8 MiB + 2 × 4 KiB guard pages).
2. The gate condition in Build161 (`size <= 8u * 1024 * 1024`) strictly excluded `0x802000`
   because 8,396,800 > 8,388,608 bytes.
3. As a result, all 24 `CallRetStacks` allocations were placed bottom-up among 16 MiB blocks.
4. Because `0x802000` leaves an unaligned offset (+8 KiB) relative to 64 KiB/16 MiB boundaries,
   subsequent 16 MiB allocations could only start at the next 16 MiB boundary, leaving
   `0x7fe000` (~7.99 MiB) dead gaps. Across 24 allocations, ~192 MiB of continuous space
   was permanently lost, reducing the maximum contiguous aligned gap to 7.93 MiB.

## Build162 changes

In `iDeck/build/ntdll-unix/virtual_ios.c` (`map_reserved_area`):
1. **Top-Down Segregation Limit Extension:**
   - Extended the segregation boundary to `size <= 9u * 1024 * 1024` (9 MiB).
   - This explicitly captures `FEXMem_CallRetStacks` (0x802000 = 8.008 MiB), `FEXMem_Frontend` (8 MiB),
     and `FEXMem_Lookup_L1` (2 MiB), routing them to the top of the arena (top-down).
   - The lower arena region remains 100% contiguous for 16 MiB blocks (`FEXMem_OpDispatcher`, JIT).
2. **64 KiB Boundary Alignment (Round-Up):**
   - For `0x802000` requests inside the published FEX arena, round the reserved size up to
     `0x810000` (64 KiB boundary).
   - This eliminates the 8 KiB unaligned tail and ensures all blocks packed at the high end
     remain cleanly aligned to 64 KiB multiples.

## Package conditions

- Base IPA: `build161-artifacts/iDeck-Build161-FEXPlacement.ipa`.
- Only `virtual.o` and archive index changed in `libntdll_unix.a`.
- All FEX objects and archives remain untouched.
- Restricted entitlements: `com.apple.developer.kernel.increased-memory-limit` and
  `com.apple.developer.kernel.extended-virtual-addressing` omitted from code signatures.
- App bundle ID: `com.kimdongup.ideck.build149`, `CFBundleVersion = 162`.
- Package hash: `candidate_sha256 = 2f4dce3ea0ad4ebf07be3bff781409f8efa339000c7619a2dc3d8092c5e2937b`.

## Hardware result

Executed on 2026-11-05 23:31:11 HST (`capture-20261105-233111`).
Optional entitlements remained absent (`increased-memory-limit: false`,
`extended-virtual-addressing: false`).

1. **CEF Region C placement:**
   `MADEIRA_POOL_CEF_LARGE_IMAGE=1` placed 211.81 MiB `libcef.dll` into Region C at line 36710:
   `[pool-cef-large] result=placed want=0xd3d0000 c_used=0x300c000 c_size=0x1c000000 code_reserve=0x1400000 available_mb=1098`.
   Main JIT pool exhaustion (`[jit-pool] EXHAUSTED`) was 0.

2. **Top-down small & medium segregation:**
   `[fex-small-topdown]` successfully placed all qualifying thread allocations:
   - `want=0x804000` (CallRetStacks, rounded to 16 KiB host page): `result=placed`.
   - `want=0x800000` (Frontend): `result=placed`.
   - `want=0x200000` (Lookup_L1): `result=placed`.
   - Sub-64 KiB thread structures: `result=placed`.

3. **Arena geometry & fragmentation recovery:**
   - Published arena size: `0x80000000` (2,048 MiB).
   - Covered space reached **`0x7edea000` = 2,029.91 MiB (99.12% utilization)**.
   - Remaining free space was reduced to only **`0x1216000` (18.08 MiB)**.
   - Lower region (`0x705c000000` to `0x70bfffffffff`) packed **100 consecutive 16 MiB views
     (1,600 MiB)** without a single unaligned dead gap.
   - All 26 `CallRetStacks` (0x802000/0x804000) and thread-local structures were cleanly
     concentrated in the upper band (`0x70d0000000..0x70dbad0000`).
   - The ~192 MiB dead-gap fragmentation observed in Build161 was **completely eliminated**.

4. **Failure analysis at 99.1% saturation:**
   - First allocation failure was delayed by >3,000 lines (to line 46466), occurring only after
     the 2 GiB arena was 99.1% full.
   - The failure was not caused by fragmentation, but by **virtual capacity saturation of the
     2 GiB limit** caused by CEF spawning repeated helper processes/threads (accumulating 100
     individual 16 MiB views, plus 26 threads × ~34 MiB per thread).
   - Unhandled access violations (`C0000005`): **0**.
   - Peak sampled physical footprint: 3,226 MB.

## Next steps

1. **Suppress CEF Process/Thread Duplication:**
   Steam CEF helpers are restarted or spawning multiple renderer/utility processes, each claiming
   independent FEX dispatchers and thread pools. Passing Chromium flags to constrain helper process
   count (e.g. `--renderer-process-limit=1`, `--single-process`, `--in-process-gpu`) or disabling
   excessive worker threads in `madeira.cfg` will keep total allocation well within the 2 GiB arena.
2. **Reclaim / Retire Inactive Thread Structures:**
   Investigate whether dead thread call-return stacks and FEX memory blocks can be released on
   thread termination so that capacity does not monotonically grow to the 2 GiB ceiling.
