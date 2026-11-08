# Steam64 Builds177–178: verified limits and soft-pool overlap repair

2026-11-06 HST. Continuation of [Builds174–176](STEAM64_BUILDS174_176_ANALYSIS_2026-11-06.md).
Target: iPhone15 Pro Max, iOS27.0.1. App ID remains
`com.kimdongup.ideck.build149`; app data and the existing Steam prefix are retained.

## Build177: what the device actually established

The device reported installed build177 and the retained run PID5182. A fresh
capture at 11:49 has SHA256
`13ec837bb7c131e469db4bbcb0bbe6f424645fbbfe9bd56fe5af27b51710827b`.
It shows both increased-memory-limit and extended-virtual-addressing false.
That verifies the runtime entitlement set; it does not independently establish
Personal Team enrollment or a fresh free-account provisioning workflow.

- Four `SUPPRESSED bulk free` events prove the bulk-free guard executed. This is
  narrower than proof that all executable-range invalidation is correct.
- The published FEX arena is **1,536 MiB**. At its first failed 16 MiB request,
  181 live views cover `0x5eb30000` bytes; only `0x14d0000` (20.81 MiB) is free,
  and the largest eligible gap is `0xc90000` (12.56 MiB). The arena is about
  98.65% occupied. This is still virtual-space exhaustion.
- Sampled physical footprint peaks at 2,090 MiB and remains about2,085 MiB.
  A lower physical sample does not repair a failed contiguous virtual request.
- No `Unhandled exception code` is present in this retained capture. Absence of
  that message does not prove browser readiness or forward progress.
- The current `cef_log.txt` is empty, and the captured screen is a blank Wine
  desktop. Login acceptance has not been achieved.

Therefore the earlier report's wording that memory exhaustion was eliminated
must be restricted to the measured earlier interval. It is not a final Steam64
acceptance claim. Two other iDeck installation variants were still running on
the device; they were not stopped during this verification.

## Concrete defect: overlapping soft reservations

Build177 sequentially returned these simultaneously active soft pools on the
same helper thread:

| Pool | Half-open range | Size |
|---|---|---:|
| First | `[0x7100000000,0x7140000000)` | 1 GiB |
| Second | `[0x7110000000,0x7150010000)` | 1 GiB +64 KiB |

They overlap by **768 MiB**. Later release/retry sequences produce additional
768.0625 MiB overlap events in a replay of the grant/release ledger.

The candidate scan advances by256 MiB while `ios_soft_slot_taken()` only tests
whether start addresses are equal. Different starts therefore admit overlapping
variable-sized pools. Summing successful `jumbo#` grants cannot establish two
independent live 1 GiB reservations; that counter also accumulates retries.
These are soft virtual bookkeeping grants, not proof of contiguous physical
memory or future commit success.

## Build178 repair

`virtual_ios.c` adds full half-open interval conflict checking to all four
variable-size soft-pool candidate sites, rejecting zero/overflowing sizes and
malformed recorded intervals. Adjacency remains valid. The separate legacy
nested-cage slot policy is retained.

`ios_soft_release()` now requires the actual allocation base. Build176 already
records the returned base, so accepting an arbitrary interior pointer is both
unnecessary and capable of releasing the wrong pool.

The patch addresses the demonstrated sequential overlap. It is not a complete
concurrent reservation broker, nor a proof that every chosen soft address can
later be committed by the kernel. Those properties still require separate
validation. The independent FEX arena capacity failure also remains an
acceptance requirement.

The actual helpers are compiled by `tests/host/check-soft-pool-ranges.py` under
AddressSanitizer/UndefinedBehaviorSanitizer. Tests cover the recorded overlap,
left/right intersections, legal adjacency, size overflow, malformed recorded
ranges, exact-base release, interior-release rejection without ledger mutation,
and release/reuse. All pass. The native compile and incremental Xcode build pass.
Only `virtual.o` object code changes in the native archive; the prior archive is
preserved locally. Existing FEX source modifications are retained, not changed
in this verification. Every DLL/EXE payload asset is frozen byte-for-byte to the
validated Build177 IPA before packaging Build178.

## CPU-count comparison not admitted

The original configuration was saved and `cpu-count = 1` was applied with exact
readback. CoreDevice failed the launch request; the script restored the original
configuration on failure, and an additional explicit restoration/readback passed.
Subsequent review found that both retained Build177 baseline logs already report
one processor, despite no `cpu-count` key in the saved configuration. Build178
also reports one. The attempted setting was redundant and this run is not an
accepted CPU-count performance or memory comparison. Reducing reported CPU count
is therefore not an untested remedy for these captures.

## Build178 hardware result

Same-ID update installation verified build178, launched PID5196. Both actual
app/helper signatures omit the optional memory entitlements; the device log
also reports both false. All **1,302 DLL/EXE assets** match the Build177 package.
The signed IPA hash and native source/object provenance are retained.

The 12:00:24 capture has SHA256
`dc7d06c131bbf519d4c08ef4c02bc0d7f8200d41c4ec421e3b16eaf4f1ba93a6`.
Replay finds six soft grants and four releases with **zero active-range overlap**,
compared with four overlap events in the Build177 capture. The second pool now
uses `0x6000000000`, disjoint from the first at `0x7100000000`. Release/retry reuse
is visible, without `[free-refused]` or soft-pool collision diagnostics. Retained
release messages show zero committed bytes; future commit viability at the low
soft address is still unproven.

The run remains blocked by FEX virtual capacity. This launch obtains a
**1,456 MiB** arena (`size=0x5b000000`), rather than Build177's1,536 MiB. Its first
failed request is **9 MiB** (`0x900000`, alignment64 KiB). There are171 live views,
`0x59f14000` bytes covered and `0x10ec000` (16.92 MiB) free, but the largest
eligible hole is only `0x6e0000` (6.875 MiB). Sampled physical footprint peaks at
2,174 MiB. No unhandled-exception or image-pool-exhaustion messages occur in this
capture, but the screenshot is still a blank Wine desktop.

Different ASLR placements and different arena sizes prevent a strict performance
or capacity A/B conclusion. The demonstrated improvement is elimination of the
recorded sequential soft-pool overlap, not Steam login or all memory failures.
The prefix has evolved across tests and was not restored to a fixed snapshot.

## Next focused target

The Build177 failure census contains59 live 16 MiB views with flags`0x3`, totaling
944 MiB. Their partly uncommitted bytes remain reserved inside live allocations;
they cannot safely be reclaimed as free space. The FEX rpmalloc source uses a
fixed16 MiB span size, making allocator span demand a concrete attribution target.
Confirm ownership/lifetime of those views before changing span sizes. A smaller
span experiment must also validate large-page size classes, alignment/mask
arithmetic, cross-thread ownership and allocation-failure handling. Changing only
`SPAN_SIZE`, freeing idle-looking live views, or repeating the CPU-count setting
is not a supported fix. No such FEX modification was made in this pass.

`diagnostics/steam64-provider-fix-20261105/analyze-soft-pools.py` regenerates the
categorical grant/release replay, overlap counts, FEX first-failure geometry,
physical samples and hashes for the retained captures.

Local evidence: `build177-artifacts/verification-20261106` (private captures,
categorical summary, screenshot and reversible comparison script), and
`build178-artifacts` (native provenance, build log, signed package and device
captures). Raw logs, profiles, device identifiers and Valve assets stay out of
this report. No commit or push was made in this verification pass.

Final cleanup: device configuration readback matches the saved original byte-for-byte. The launched Build178 PID was still present; no unguarded termination was attempted.

After normalizing the CoreDevice app URL, final cleanup status: `normal-termination-requested` for the exact launched PID5196. Other app variants were left untouched.

## Entitlement-independent feasibility review

[추가 메모리 권한 없는 실행 가능성 검토와 FEX 예약 조사](STEAM64_NO_EXTRA_MEMORY_REVIEW_2026-11-06.md)는 예약·커밋·물리 사용을 구분하고, 16 MiB 범위의 실제 점유 및 오래된 수명 추적 결함을 확인한다. 새 계측은 호스트 검사·컴파일만 완료했으며 Build178에 설치된 변경으로 간주하지 않는다.
