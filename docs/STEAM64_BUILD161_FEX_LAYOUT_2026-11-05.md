# Build161: segregated FEX arena placement

2026-11-05 HST. Follow-up to [Builds158–160](STEAM64_BUILDS158_160_MEMORY_2026-11-05.md).
The user requested continuing documentation and a focused investigation within a
limited remaining budget. No broad rebuild or FEX source modification is used.

## Question and prior evidence

Build159 placed the 211.81 MiB CEF image in region C without either optional
memory entitlement, then failed a 16 MiB aligned allocation inside its 2 GiB
FEX arena. Aggregate arena free space was 134.11 MiB, but its largest aligned
hole was only 11.69 MiB. Build160's 3 GiB reservation was rejected; reporting two
processors did not prevent the arena failure. Both unsuccessful experiments
remain off. V8 jitless and L1-only FEX lookup caches were already active.

The retained trace has exactly 3,000 `[valloc]` records before the first census;
logging is capped. `[vname]` records report allocation labels without complete
free/lifetime evidence. Replaying those records as a complete live map or
summing labels as concurrent usage would be invalid. Reserved but uncommitted
bytes inside a live view are also not free holes and must not be reclaimed.

## Controlled native experiment

`MADEIRA_FEX_SMALL_TOPDOWN=1` changes the Wine reserved-area placement preference
for requests of 1 byte through 8 MiB, only when their entire explicit address
range lies inside the published FEX arena and the caller requested bottom-up.
Those requests try top-down first, then their original bottom-up direction on
failure. Larger requests keep their existing placement. The hypothesis is that
packing small requests from the upper end preserves aligned lower runs for
16 MiB consumers. This is a hypothesis, not a proven general allocator policy.

The existing allocator still enforces mapping success, requested alignment,
bounds, reserved-area exclusivity and view ownership. No live allocation is
moved/freed, no protection check is bypassed, and no address range is expanded.
The flag is default-off. In particular, the older broad WoW64-band admission
exception is not used as proof that a request is inside the published arena.

`MADEIRA_FEX_VIEW_LOG=1` adds a one-time list of live views to the existing
failure-only census. Each entry includes clipped address, size, view flags and
committed bytes measured from Wine's protection bookkeeping. At most 512 entries
are emitted, with an explicit truncation marker beyond that bound. No guest
payload is read. Normal/default census output remains unchanged.

## Package and execution conditions

- Build161 updates the existing same-ID app; app data and prefix are preserved.
- Retained Build152 native inputs and the proven baseline-object reproduction
  are reused. Only `virtual.o` and archive index metadata change among 105
  link inputs; all FEX objects/archives remain unchanged.
- The actual app/helper signatures omit increased-memory-limit and extended
  virtual addressing. Existing development debugging/JIT setup remains.
- Launch flags: large CEF C placement on, small-allocation top-down on, live-view
  logging on, unsuccessful 3 GiB rung off. CPU-count override is absent.
- Source/native provenance, package hash, signature checks and private device
  captures are retained under local `build161-artifacts`.

## Validation

`tests/host/check-fex-small-topdown.py` compiles the actual placement wrapper with
allocator stubs under AddressSanitizer/UndefinedBehaviorSanitizer. Fifteen cases
cover default-off/exact opt-in, inclusive size bound, zero size, foreign/extended
ranges, absent arena, original top-down requests, unchanged bounds/alignment/
protection arguments, successful preference, original-direction retry, and total
failure propagation.

`tests/host/check-fex-arena-census.py` verifies the existing clipping/protection/
overlap/alignment/overflow accounting and the new opt-in clipped-view dump.
These checks validate dispatch and diagnostics, not real-device fragmentation
improvement. The native iOS compile and isolated debug-dylib relink pass.

## Hardware result

Executed on 2026-11-05 23:12:43 HST (`capture-20261105-231243`). Both optional memory
entitlements remained absent (`increased-memory-limit: false`,
`extended-virtual-addressing: false`).

1. **CEF Region C placement:**
   `MADEIRA_POOL_CEF_LARGE_IMAGE=1` placed the 211.81 MiB `libcef.dll` image into
   Region C at line 36727:
   `[pool-cef-large] result=placed want=0xd3d0000 c_used=0x300c000 c_size=0x1a000000 code_reserve=0x1400000 available_mb=1123`.
   `[jit-pool] EXHAUSTED` was 0. Main JIT pool exhaustion was completely avoided.

2. **Top-down small allocation:**
   `[fex-small-topdown]` executed 8 times, all returning `result=placed`.

3. **Arena allocation failures:**
   Two allocation failures occurred inside the 2 GiB FEX arena (`0x7059cc0000..0x70d9cc0000`):
   - Line 43421: `[va-scan] FAILED size=0x802000 align=0x10000` (8.0078 MiB, 64 KiB align).
   - Line 44773: `[va-scan] FAILED size=0x1000000 align=0x10000` (16.0 MiB, 64 KiB align).

4. **Census and 222 Live Views Dump (`MADEIRA_FEX_VIEW_LOG=1`):**
   - Published arena size: `0x80000000` (2,048 MiB).
   - Covered space: `0x7309a000` (1,840.6 MiB, 89.9% of total arena).
   - Aggregate free space: `0xcf66000` (207.4 MiB) divided across 106 holes.
   - Largest gap: `0x7fe000` (7.992 MiB); largest aligned gap: `0x7f0000` (7.9375 MiB).
   - Dominant allocations:
     * `0x1000000` (16 MiB): 91 views (1,456 MiB total; primarily `FEXMem_OpDispatcher` and `FEXMemJIT`).
     * `0x802000` (8.0078 MiB): 24 views (`FEXMem_CallRetStacks`, 8 MiB + 2 × 4 KiB guard pages = 192.2 MiB total).
     * `0x800000` (8 MiB): 17 views (`FEXMem_Frontend` = 136 MiB total).
     * `0x200000` (2 MiB): 25 views (`FEXMem_Lookup_L1` = 50 MiB total).

5. **Root cause of fragmentation and starvation:**
   - `FEXMem_CallRetStacks` requests `0x802000` bytes (8 MiB + 8 KiB). The 8 KiB unaligned tail breaks 64 KiB / 16 MiB boundary alignment for the subsequent 16 MiB allocations, causing 24 dead gaps of `0x7fe000` (~7.99 MiB each, cumulative ~192 MiB lost to unaligned gaps).
   - Per-thread FEX structures total ~34 MiB per thread (`FEXMem_OpDispatcher` 16M + `FEXMem_Frontend` 8M + `FEXMem_CallRetStacks` 8.01M + `FEXMem_Lookup_L1` 2M). With >20 threads spawned by Wine/CEF, the 2 GiB arena is virtually filled to 90% capacity, leaving no contiguous >=8 MiB or >=16 MiB space.

6. **Process stability & UI state:**
   - Unhandled exceptions: 0 (no `C0000005` or `C000001D` crashes).
   - Sampled peak physical footprint: 3,079 MB.
   - UI remained a blank Wine desktop; Steam login window did not appear because thread initialization / helper setup stalled on the arena memory allocation failures.

## Next targeted investigation

1. **CallRetStacks alignment / sizing:**
   Align `FEXMem_CallRetStacks` to a clean 64 KiB boundary (e.g. `0x810000` or rounding allocation size to 64 KiB/1 MiB) or isolate it from the 16 MiB JIT/OpDispatcher arena band so it does not fragment the arena into sub-8 MiB holes.
2. **CallRetStacks allocation band steering:**
   Check whether `ios_fex_band_base` can accommodate separate sub-arenas or dedicated buckets for 16 MiB blocks vs small/medium thread structures, or whether inactive threads' call-return stacks can be safely reclaimed.
