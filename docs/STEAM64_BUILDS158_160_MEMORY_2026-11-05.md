# Steam64 memory experiments, Builds158–160

2026-11-05 HST. Follow-up to `STEAM64_BUILDS153_157_RESULTS_2026-11-05.md`.
These are local experimental packages. The initial large-image allocation has
been demonstrated; login acceptance has not been achieved.

## Constraint and signing evidence

Both optional memory entitlements are removed from the **actual app and helper
signatures** for these candidates:

- `com.apple.developer.kernel.increased-memory-limit`
- `com.apple.developer.kernel.extended-virtual-addressing`

Development debugging (`get-task-allow`) and the existing JIT helper remain.
Build158 and Build159 runtime logs report both optional entitlements false.
The retained development provisioning profile still permits increased memory;
these tests exercise signatures without that entitlement. They do **not** prove
Personal Team enrollment, a fresh free-account provisioning flow, or seven-day
renewal. No developer membership tier is inferred from profile lifetime.

Apple describes the [increased memory entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit)
and [extended virtual addressing entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.extended-virtual-addressing)
separately. Neither is required by the allocator experiments below. JIT enabling
still uses the existing development/debugger mechanism.

## Build158: unchanged native code, restricted entitlement set

The Build157 payload was repackaged without either optional entitlement; its
native debug dylib stayed byte-identical to Build152. Same bundle ID update
installation preserved the Wine prefix and Steam update.

- The first launch stopped during JIT pool placement before Wine startup. A new
  launch of the identical package reached Wine and CEF. This is an ASLR/layout
  variable, not evidence that the removed entitlement alone caused that stop.
- The longer capture sampled a 2,754 MB physical footprint, without a large-image
  pool-exhaustion event. It did record an 8 MiB constrained allocation failure
  inside the 2 GiB FEX arena. A quiet/blank desktop is not login acceptance.
- No new JetsamEvent was found in the inspected crash-log listing. That does not
  establish a universal memory ceiling or prove the exact exit reason.

## Build159: one bounded CEF image in region C

`MADEIRA_POOL_CEF_LARGE_IMAGE=1` prefers existing debugger-prepared region C for
an exact, case-insensitive `libcef.dll` basename, plain AMD64 PE image, allocation
larger than 16 MiB and no larger than 224 MiB. The allocation must be 16 KiB
aligned. Malformed/unreadable/hybrid PE headers fail closed.

The path retains the atomic cursor shared with FEX code buffers, ownership ledger,
live-code exclusion and ordinary fallback/reuse guards. It leaves at least
20 MiB for code buffers (one 16 MiB buffer plus 4 MiB margin). This is a minimum
reserve, not a guarantee of enough code-cache space for the whole session.
`MADEIRA_POOL_LOW_IMAGES` retains its existing separate small-image policy.
Both new large-image placement and the later 3 GiB arena rung are default-off.
No additional OS executable region is created by this placement path.
For this experimental native package, the config spelling is
`env.MADEIRA_POOL_CEF_LARGE_IMAGE = 1`; omit it or use `0` to retain the original
allocation preference. The controlled runs injected this flag only for the
launch; the device's original configuration was not permanently enabled.

Observed native diagnostic:

```text
[pool-cef-large] result=placed want=0xd3d0000 c_used=0x300c000 c_size=0x1e000000 code_reserve=0x1400000 available_mb=1276
```

This proves one **211.81 MiB** image allocation in an existing 480 MiB region C.
The image-copy diagnostic also identifies `libcef.dll`, region C, and pure x86-64.
It does not prove a complete browser, a safe general-purpose image-sharing
scheme, or repeated login success.

The subsequent failure order in the retained 8,471,413-byte capture is:

1. CEF placed in C (line36616).
2. FEX arena could not satisfy an aligned 16 MiB request (line44683).
3. First helper unhandled null-read access violation (line45137).
4. A restarted helper found C full enough to refuse a second image, but its main
   pool fallback succeeded (line54231).
5. Later retries exhausted image storage again (line62152 onward).

The first FEX census covers a 2 GiB arena: 1,913.89 MiB in live views,
134.11 MiB free across holes, and a largest **aligned** gap of 11.69 MiB.
The 16 MiB request cannot fit despite aggregate free space. These are virtual
bookkeeping bytes, not physical residency. The null-read occurs after this
allocation failure; the ordering supports an allocation-related failure path,
but does not alone identify the exact dereference's implementation.

Steam single-process and V8 jitless were verified applied in the log. The repeated
large loads here are helper restarts, not proof that those switches were absent.
Sampled physical footprint peaked at 3,218 MB; reported available memory dropped
to 99 MB during retries. No fixed free-account limit is assumed. The screenshot
remained a blank Wine desktop. Persistent code-buffer last-page mprotect warnings
also remain and require separate investigation.

## Build160: try the missing 3 GiB arena rung

The existing native reservation ladder tries 16, 8 and 4 GiB sizes before falling
back to 2 GiB. Build159 fell through all larger candidates to 2 GiB, then ran out
of aligned space inside it. `MADEIRA_FEX_ARENA_3GB=1` adds one 3 GiB reservation
attempt just before that 2 GiB fallback. It respects the existing `arena-mb` cap,
checks native placement against the task ceiling, and publishes only the actual
registered range. A failed reservation keeps the original fallback behavior.
This reserves address space as `PROT_NONE`; it does not eagerly commit 3 GiB RAM.
It may still compete with CoreAnimation or guest address space, so it remains an
explicit experiment. FEX source is unchanged.

The hardware rejected the 3 GiB native reservation with `kr=3` and fell back
to 2 GiB. The first capture again confirms the 211.81 MiB CEF image placed in C,
this time with a 432 MiB region C and both optional runtime entitlements false.
At 2,714 MB sampled physical footprint, a 16 MiB aligned FEX request failed;
the largest aligned hole was 10.06 MiB. No unhandled access violation or image
pool exhaustion had appeared in that early capture. This result rules out the
3 GiB rung as an effective remedy for this launch; it must not be represented
as an increased arena or successful CEF startup.

The later ordinary-CPU capture reached 3,278 MB sampled physical footprint.
A further same-package run disabled the unsuccessful 3 GiB option and used the
existing `cpu-count = 2` Wine setting. The runtime confirmed two reported
processors (host six). CEF's 211.81 MiB C placement again succeeded, but the
2 GiB arena again failed a 16 MiB aligned request. This capture also contains
three unhandled `C000001D` reports during helper retries; they are not counted
as three independently diagnosed root causes. Sampled footprint reached
3,342 MB. Different ASLR layouts and failure stages prevent a strict
performance/peak-memory A/B comparison, and the CPU setting did not satisfy
acceptance.

The original configuration was restored and device readback was byte-identical
to the saved original. No prefix reset or FEX modification was made. At the
final process listing the launched host PID was already absent, so no normal
termination was sent to that PID. The inspected crash directory supplied no
new host-exit report attributable to this run; a same-date Madeira report was
from the earlier Build153 session. The precise host-exit cause is not established.

| Run | Large CEF C placement | FEX reservation | Outcome |
|---|---|---|---|
| 158, second launch | Disabled | 2 GiB | 8 MiB arena request failed; blank desktop |
| 159 | One 211.81 MiB image | 2 GiB | 16 MiB arena failure, null-read, helper restarts, later image exhaustion |
| 160, 3 GiB option | One 211.81 MiB image | 3 GiB refused; 2 GiB fallback | 16 MiB arena failure; no login acceptance |
| 160, CPU count two | One 211.81 MiB image | 2 GiB | Arena failure and helper retry exceptions; original config restored |

## Native provenance and validation

Public main differs from the preserved Build152 native source. The native
experiments therefore do not use an ordinary full Xcode build from main:

- Export the native build inputs from retained source commit
  `c7f59d6812c9b78f4ca9b46c2cb987662f777d81`.
- Recompile unmodified `virtual_ios.c` with the original flags and verify the
  resulting object **byte-for-byte** against the original archive member:
  `e97e0c2c47b7e7460ca021de16df3ea75a42fe2a687679f07d2cc41edf679e23`.
- Apply the reviewed source patch without fuzz, recompile only that unit, and
  replace `virtual.o` in a disposable `libntdll_unix.a` copy.
- Preserve all other compiled objects/archives among 105 debug-dylib link inputs.
  Build160 also updates the archive symbol index; no other object code changes.
- Relink and re-sign a disposable package, check permitted payload changes,
  nested signatures, absent optional memory entitlements and IPA CRC/hash.

The policy host test passes under AddressSanitizer and UndefinedBehaviorSanitizer:
name/flag/alignment/size boundaries, recorded region-C capacity, competing
16 MiB code allocation, integer overflow, and 100,000 capacity cases against a
128-bit arithmetic oracle. Existing malformed-PE/media fixtures pass; packaged
crypto/provider/forwarder closure passes across 74 modules. Full existing media
farm acceptance remains unrun because main's unrelated `mf.dll` is missing.

Local package manifests, relink provenance JSON and private CoreDevice captures
are retained under `build158-artifacts`, `build159-artifacts`, and
`build160-artifacts`. `diagnostics/steam64-provider-fix-20261105/analyze-memory-runs.py`
regenerates categorical counts, hashes, allocation events and failure ordering.
Raw logs, signing material and Valve binaries are not included in this report.
These native/runtime observations use ordinary compiler/CoreDevice tools; earlier
REA plist Evidence is only metadata evidence.

## Next investigation supported by these runs

The first large image no longer needs to fit the fragmented main pool. The next
useful work is a **live allocation/owner census inside the 2 GiB FEX arena**,
followed by a bounded change that reduces reserved space or fragmentation.
The existing first-failure census already shows 75 views of 16 MiB with flags
`0x3`, plus 19 committed views of 16 MiB with flags `0x23` in Build159. Correlate
those live views with allocator names and owner lifetimes before reclaiming or
moving anything. Separate cumulative allocation-name events from live views;
their counts are not interchangeable. L1-only lookup-cache mode was already
active, so proposing that setting again would not address this run.

The rejected 3 GiB reservation and CPU-count test are retained as negative
results. Do not enable them by default or report them as successful remedies.
Stopping futile browser restarts and proving reclamation of dead generations
can bound secondary memory growth, but cannot itself make the first helper's
failed allocation succeed. Changes to FEX itself must respect its contribution
policy; no FEX source was changed here.

## Acceptance still required

A successful initial C allocation is a useful intermediate result. Acceptance
requires the first helper to survive initialization, no image exhaustion across
subsequent intended loads, physical usage within the measured normal limit,
visible login UI, and repeated cold starts. Do not share one mutable/relocated
image between pseudo-processes or skip pure-x64 copies without a separate
relocation/private-data/dispatch analysis. Existing source records a prior FEX
RIP alias regression when image copies were skipped.

Rollback uses a retained same-ID package without uninstalling or clearing the
prefix. It does not reverse the Steam updater's client changes.

## Next executed experiment

See [Build161 FEX layout experiment](STEAM64_BUILD161_FEX_LAYOUT_2026-11-05.md) for the default-off native placement experiment and continuing results.
