# iDeck Build 124 — Glyph Cluster execution handoff

> Status: execution instructions only; not proof that Build 124 has compiled or run.
> Prepared: 2026-11-03 (Pacific/Honolulu).
> Repository: https://github.com/kimdongup/iDeck
> Instruction branch: handoff/build124-glyph-cluster-20261103
> Primary working branch reported previously: work/build101-canonical-20261101.
> Language for user-facing progress and final report: Korean.

## 0. Your assignment

You are the **execution agent (Glyph Cluster)**. Advance the existing iDeck Steam Big Picture / WoW64 runtime experiment from Build 123 to Build 124, preserving all prior work. First audit the actual local source and build configuration; then make the smallest technically justified changes, build and validate on macOS if that host is available, and produce verifiable evidence and an actionable continuation report. Prioritize **real execution over speculative status updates**. Do not mark a step done without its actual command results.

This document is NOT a request to reimplement iDeck, reset the project, or replace the existing Wine/FEX work. Do not assume the published GitHub source already includes the user's latest local patches.

### Safety and change boundaries

- **Never** run git reset --hard, git clean -fdx, forced checkout, git submodule update --force, or destructive cache cleanup.
- Preserve uncommitted changes in the root repo, FEX submodule, Wine submodule, DXMT, and local scripts. Do not overwrite or revert them.
- Record git status and all diffs before modifying code; back up changed files before any risky edit.
- Do not push local code, change remote history, invoke GitHub Actions, release an IPA, or install/uninstall on the iPhone without user authorization for the respective action. This handoff authorizes analysis, non-destructive local patches, audits, tests, and builds; it does **not** authorize destructive operations.
- Never publish signing material, access credentials, UDIDs, personal logs, local private paths, or entire build artifacts into the public repository.
- Use the external APFS SSD for DerivedData, logs, test artifacts, and package staging; do not fill the Mac internal system disk.
- If only a Linux container is available, perform source audits and tests there and provide explicit Mac execution commands; do NOT falsely claim an Xcode or iPhone validation.

## 1. Environment and known state: verify, do not blindly trust

**Reported user Mac workspace**

- ROOT=/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
- WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
- Linux container mount: /shared/iDeckRuntimeLab/iDeck
- Mac: Apple Silicon M1, Xcode 27.2.
- Local root HEAD reported: 574d24e (abbreviated). GitHub instruction-branch base was e07843b0fe9ad97d26d35713a4a4e516fc29457e. **These are different.** Do not automatically pull the instruction branch into the local working branch or assume fast-forward history.
- Last successful Build 123 IPA was built and installed. Current phone UI remained at “connecting steam controls…”.
- Build 123 canonical native library preflight: 13/13 libraries, FEX 7/7, Wine i386 farm pending=0, StikJIT verified, Wine prefix and VC++ x64 runtime verified.
- Local **build124-on-mac.sh** was generated under tools/dev-build101/ from build123-on-mac.sh. Its --audit completed successfully; this is not a compiled Build 124.
- Build 123 script invokes build123-dxmt-on-mac.sh and existing i386 farm machinery, which may still output Build123 labels. This is a reused dependency, not proof Build 124 is assembled.
- Build 123 used CURRENT_PROJECT_VERSION=123 and MARKETING_VERSION=0.1.19. Build 124 target: 124 and 0.1.20, same existing Bundle ID, same signing configuration (without exposing signing identifiers in reports).
- Build 124 expected IPA output: $WORK/build124-artifacts/Output/iDeck-WoW64-Build124-Debug.ipa.
- The user completed a **FEX guard probe source patch**. Expected local modified FEX files: FEXCore/Source/Interface/Core/CPUBackend.cpp, FEXCore/include/FEXCore/Utils/ThreadPoolAllocator.h, and preexisting Source/Windows/WOW64/Module.cpp.
- The user completed an **opt-in FD guard source patch** to build/ntdll-unix/server_ios.c; check for MADEIRA_FD_CACHE_CROSS_GUARD and ios_fdt_guard_cross_cache_close. Default behavior is OFF. Backup created in build124-backups/ (verify).
- Existing Wine submodule was modified before these diagnostic patches; preserve it.
- No verified Build 124 IPA compilation or on-device run exists as of this handoff.

## 2. Failure evidence from Build 123 (not Build 124)

The full run had 38,510 lines, marker 123. Counts below are diagnostic matches from that run:

| Observation | Count | First log line |
|---|---:|---:|
| steamwebhelper spawn | 9 | 3399 |
| CEF check.cc(376) NOTREACHED | 4 | 8032 |
| Crashpad nonresponse | 3 | 14801 |
| BrowserReady observed | 0 | — |
| FEX last-code-buffer-page mprotect failure | 234 | 1899 |
| FEX store-noalias | 8 | 10358 |
| FEX store-undecoded | 1 | 17779 |
| memory access fault | 7 | 10359 |
| 16MiB aligned allocation failure | 6 | 31949 |
| fdtrace CROSS! cross-PEB records | 49 | 22290 |
| touch accepting=1 | 0 | — |

**Observed ordering:** FEX mprotect warning (line 1899) → first CEF NOTREACHED (line 8032) → first store-noalias and memory fault (line 10358-10360) → first cross-PEB FD log (line 22290) → late FEX aligned allocation failures and NULL access faults (~31949-32493).

**High-VA data:** 16 GiB FEX virtual reservation arena occupancy reached 94% (15,512 MiB used, 871 MiB free, 1,876 views). Snapshot logged 606 16MiB views. These are **virtual reservations, NOT physical RAM usage**. FEX has some FREE records; do not assert that all views leak. Determine per-process allocation and release accounting.

**Causality caution:** The first CEF NOTREACHED happens before the late address exhaustion. Fix first-failure analysis and progressive resource consumption **independently**. A CROSS! trace reports ledger ownership, but does not alone prove the ledger is correct.

**Previously observed source details:**

- FEX last-code-buffer-page VirtualProtect warnings originate in CPUBackend.cpp and ThreadPoolAllocator.h. They may be guard-page failures rather than executable mapping corruption. The new probe differentiates them; verify actual patch contents.
- Wine server_ios.c FD-cache teardown uses stored=fd+1 convention, restored real_fd=stored-1, skips FD_TYPE_INVALID; a diagnostic ledger close record precedes close(real_fd).
- Opt-in FD guard skips a cache-close only if the ledger reports another PEB, but the ledger might be stale. Keep the guard OFF in the baseline; never describe it as a proven general fix.
- Check the compiled output for current guard instrumentation. Existing preflight/static library presence does NOT prove modified source was recompiled and linked.

## 3. Phase A — save evidence and verify source before building

Run on Mac, from a **valid** working directory. If only Linux is available, adapt ROOT to /shared/iDeckRuntimeLab/iDeck and skip all xcodebuild/devicectl commands.

~~~bash
set -euo pipefail
ROOT=/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
cd "$ROOT"
STAMP=$(date +%Y%m%d-%H%M%S)
EVIDENCE="$WORK/build124-artifacts/evidence/$STAMP"
mkdir -p "$EVIDENCE"
git rev-parse --abbrev-ref HEAD | tee "$EVIDENCE/branch.txt"
git rev-parse HEAD | tee "$EVIDENCE/head.txt"
git status --porcelain=v1 -uall > "$EVIDENCE/root-status.txt"
git diff --binary > "$EVIDENCE/root-working.diff"
git -C FEX status --porcelain=v1 -uall > "$EVIDENCE/fex-status.txt"
git -C FEX diff --binary > "$EVIDENCE/fex-working.diff"
git -C wine status --porcelain=v1 -uall > "$EVIDENCE/wine-status.txt"
git -C wine diff --binary > "$EVIDENCE/wine-working.diff"
git diff --check
git -C FEX diff --check
git -C wine diff --check
test -f tools/dev-build101/build124-on-mac.sh
bash -n tools/dev-build101/build124-on-mac.sh
rg -n 'MADEIRA_FD_CACHE_CROSS_GUARD|ios_fdt_guard_cross_cache_close' build/ntdll-unix/server_ios.c
rg -n '\[build124-guard\]' FEX/FEXCore/Source/Interface/Core/CPUBackend.cpp FEX/FEXCore/include/FEXCore/Utils/ThreadPoolAllocator.h
bash tools/dev-build101/build124-on-mac.sh --audit | tee "$EVIDENCE/audit.log"
~~~

Do not overwrite a source file just because a string is absent. Investigate actual content and history first. Collect hashes for involved sources and libraries. The successful --audit is a prerequisite, **not** the acceptance criterion.

## 4. Phase B — prove native recompilation and linkage

1. Inspect tools/dev-build101/build124-on-mac.sh and build123-on-mac.sh, FEX/Wine build targets, and existing libraries. Inspect exact commands, compiler inputs, output paths, timestamps, and object files.
2. Determine whether the two FEX guard probe edits and server_ios.c FD guard edit are compiled into Build 124 rather than stale Build 123 static archives. If not, run the **existing targeted FEX and Wine native rebuild machinery**; do not invent target names. Capture native compiler/linker logs and archive/binary hashes.
3. Do not rebuild hundreds of DLLs just because their farm label says Build123: pending=0 was already reported. Rebuild only dependencies that truly need updating.
4. Verify the instrumentation symbols/strings in the final Mach-O or linked sections **and their runtime log emission when that code path is triggered**. Static strings alone are insufficient if dead-stripped or never executed.
5. If a native build recipe is unavailable, stop at a clear documented blocker with the exact missing command/input. Never package stale binaries as a passing Build 124.

## 5. Phase C — macOS Build 124

Do only on a Mac with Xcode, after Phase A/B checks. The script currently performs its own source marker / output checks; inspect them, do not bypass them. Use dedicated DerivedData, not Build100.

~~~bash
set -o pipefail
ROOT=/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
OUT="$WORK/build124-artifacts/Output"
cd "$ROOT"
mkdir -p "$OUT"
bash tools/dev-build101/build124-on-mac.sh --build 2>&1 | tee "$OUT/build124-console.log"
~~~

Expected independent outputs:
- $WORK/build124-artifacts/DerivedData/iDeckBuild124 (or actual Build124 isolated path verified in script)
- $WORK/build124-artifacts/Output/iDeck-WoW64-Build124-Debug.ipa
- $WORK/build124-artifacts/Output build and packaging logs
- An evidence report that identifies changed native library archive hashes **before vs after**.

If ditto IPA packing fails despite successful Xcode compilation and staging, use the existing user-provided build124-repack-ipa.py **only after checking its script content, signing verification, Payload layout, and staged Build 124 version**. Do not claim packaging success unless the ZIP and signature really validate.

On an IPA that exists, at minimum validate:
~~~bash
IPA=/Volumes/Repository/cokacremote/iDeckRuntimeLab/build124-artifacts/Output/iDeck-WoW64-Build124-Debug.ipa
test -s "$IPA"
unzip -tq "$IPA"
shasum -a 256 "$IPA"
unzip -p "$IPA" Payload/Madeira.app/Info.plist >/dev/null
~~~

Also verify Info.plist CURRENT_PROJECT_VERSION equivalent=124, signing validity of extracted .app, and the executable/native instrumentation. Do not assume the Mach-O executable is always named Madeira; inspect actual Payload contents.

## 6. Phase D — device A/B experiments (only after explicit user approval)

This assignment does **not** authorize automatic device install or removal. After approval:

- Collect a **fresh** runtime session from the physical iPhone; ensure build marker=124 and distinguish madeira-log.txt from madeira-log.prev.txt. Never compare historical Build122/123 records as new 124 results.
- First experiment = default FD guard OFF (baseline). Record CEF NOTREACHED first occurrence, process spawn, crashpad status, FEX mprotect guard diagnostic by origin, FD CROSS, FEX VA use and 16MiB allocation failures, wine process exits, and BrowserReady.
- Second experiment = MADEIRA_FD_CACHE_CROSS_GUARD=1 **inside the device app's actual runtime environment**, not only exported in the Mac Terminal. If injection requires changing app code/launcher, use a separate labeled experiment and rebuild. Record [fd-guard] SKIP count, FD reuse/close ledger health and resulting client process behavior.
- Preserve full logs locally and compare first-failure times, process lifetimes, and per-PEB FEX allocation/free deltas. Do not optimize a late-memory failure while hiding the earlier CEF error.
- Do not claim touch/controller success until controls truly accept input on the iPhone.

## 7. Acceptance gates

| Gate | PASS condition | If not met |
|---|---|---|
| A0 Source safety | Existing local modifications preserved; diffs and hashes captured | STOP before modifying |
| A1 Native rebuild | FEX and Wine changed sources demonstrably recompiled/relinked | STOP stale artifact publication |
| A2 IPA | Build 124 bundle/version confirmed, signature valid, archive valid, correct native probes present | STOP before installation |
| A3 First failure | First CEF NOTREACHED has module/RVA/call-site evidence or a documented tracing limitation | Investigate, do not guess |
| A4 Resource lifecycle | Per-process VA and FD cleanup evidence across repeated CEF attempts | Label provisional until measured |
| A5 UI | Real BrowserReady and usable Steam Big Picture + controls on physical device | Do not claim issue solved |

A0-A2 are build-delivery gates. A3-A5 are runtime-quality gates: do not confuse a built IPA with a functioning Steam UI.

## 8. Handoff artifacts and checkpoints

Produce these **locally**, not in the public GitHub repository by default:

- BUILD124_EXECUTION_REPORT.md — concise Korean report with stage, command, observed output, pass/fail, next action.
- BUILD124_CHANGELOG.md — each changed file and why, with explicit preexisting-vs-new distinctions.
- BUILD124_VALIDATION.json — machine-readable build hashes, gates, timestamps, test counts, device run IDs (avoid full UDID in public versions).
- Detailed logs under $WORK/build124-artifacts/Output or evidence/, not mixed with Build123.
- BUILD124_NEXT_ACTION.md — exact continuation point and one or two next executable commands.

At each stage update a checkpoint including:
- Working directory, git branch, HEAD, dirty state, changed files/submodule status.
- Completed steps and verification command outcomes.
- Unresolved blockers and how to reproduce.
- Output file locations on Mac.
- What still requires user approval (device install, push, release).

Do not fabricate tests, file paths, elapsed times, commits, or “success” states. If session or model usage ends, stop with reproducible local checkpoint and no destructive cleanup.

## 9. Fetch this instruction without touching the dirty working tree

Because local HEAD 574d24e and GitHub's working-branch HEAD e07843b differ, **do not run git pull blindly**. Instead:

~~~bash
ROOT=/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
git -C "$ROOT" fetch origin handoff/build124-glyph-cluster-20261103
mkdir -p "$WORK/build124-artifacts/handoff"
git -C "$ROOT" show FETCH_HEAD:docs/handoffs/BUILD124_GLYPH_CLUSTER_EXECUTION.md > "$WORK/build124-artifacts/handoff/BUILD124_GLYPH_CLUSTER_EXECUTION.md"
~~~

This fetches the document to a **separate working file**, without merging/checking out a branch and without touching modified FEX/Wine files.

## 10. Report format for Glyph Cluster

Use this exact concise heading sequence in your final Korean report:

1. 현재 상태 — 실제 실행한 위치와 기준 commit
2. 소스 보존 확인 — git status/diffs/checkpoint
3. Build 124 컴파일 — native/static linkage, IPA and SHA-256
4. 검증 결과 — PASS/FAIL/BLOCKED with evidence paths
5. 장애 원인 가설 — observed evidence vs hypothesis separated
6. 다음 실행 명령 — short commands with accurate paths
7. 사용자 승인 필요 항목 — list only actions actually awaiting approval

**Start with Phase A now. Do not ask the user to repeat paths or constraints already included here.**
