# Steam64 on iPhone — Build 99–152 investigation and engineering handoff

**Status as of 2026-11-04 (HST):** **BLOCKED / diagnostic Build152 IPA built; device execution not yet reported.**  
**Scope:** `kimdongup/iDeck` / local Madeira + Wine + FEX + ARM64EC, on-device Windows Steam64 bootstrap.  
**Related:** [iDeck technical status](IDECK.md), [building guide](BUILDING.md), [Steam recovery](IDECK_STEAM_RECOVERY.md).  
**Classification:** Engineering handoff, not an assertion that Steam64, Big Picture or a game works in this test line.

> This report reconstructs observed logs and commands from the investigation. The live Mac checkout, ignored artifacts, Wine/FEX submodule modifications, and device app are **not automatically synchronized to GitHub**. Do not treat this document-only commit as a code fix. Keep a record of Git SHAs/diffs before rebasing or cleaning.

## 0. Executive summary

**Latest verified milestone:** Build152 IPA was successfully packaged (`BUILD152_IPA_PASS`). The iOS native NTDLL diagnostic patch was successfully compiled into `libntdll_unix.a` and appears in the Xcode **`Madeira.debug.dylib`**, not the small `Madeira` launcher executable. **No Build152 device run or `[b152-file]` runtime output is yet in evidence.**

**Current user-visible failure:** The Steam64 client on the test iPhone has shown `Steam - Fatal Error`; the Steam bootstrap log earlier recorded failure to fetch `https://client-update.steamstatic.com/steam_client_win64` after approximately 60 seconds: `Download failed: http error 0`, then `Failed to load manifest` / `Steam needs to be online to update`. This is an observed *bootstrap failure*, **not proof that Internet access, DNS, TCP or TLS is universally broken**.

**Most significant technical signals:**
1. The Steam `CHTTPClientThreadPool:0` thread repeatedly consumes ~94–95% of one sampled CPU while cycling through Wine `lookup_unix_name`, `find_file_in_dir`, `fstatat`, `getattrlistat`, `openat`, `getdirentries64`. Whether this is a causal starvation / retry loop or merely correlated work remains unproven.
2. Build151 DNS for `client-update.steamstatic.com` completed in 130 ms (four addresses). Immediately afterward a TCP port 443 connect completed with `err=0 peer=YES`; no remote-IP-to-domain socket correlation was logged. It is *likely* the update flow but not positively attributed.
3. The later `crash.steampowered.com` DNS completed in 21 ms; a separate TCP connection succeeded, and modified WinINet emitted `[b151-net] tcp connected` and `tls begin compat=0`. `secur32.dll` loaded; `[schannel-ios] gnutls_global_init = 0` and `process_attach SUCCESS` appeared. No later `[b151-net] tls initial status` was seen. The later crash-report path is distinct from the earlier Steam update request.
4. FEX logs showed `Failed to mprotect last page of code buffer` in prior runs, a plausible competing line of investigation; this is *not yet linked causally* to the Steam HTTP timeout.
5. Build151 full timeline also contains repeated `C0000005` access violations on thread `0060` **after** the fatal UI and crash-report processing, including null-address reads. Do not silently attribute them to the update request.

## 1. User-visible chronology (selected milestones)

| Build / period | Observation / evidence | Assessment |
|---|---|---|
| 99 | Initial Steam Big Picture attempt on iPhone; UI largely remained launcher/menu; multi-touch/right-click issue | Incomplete Steam runtime path |
| 100–101 | Wine process / wineserver / bootstrap work; `wine_process_started=1`, `bootstrap_server_init_ok=0`, `wine_main_exited=1`; Build101 compiled and signed, still “connecting steam controls…” | No functioning Steam64 |
| 124 | “connecting steam controls…” persisted | Symptom persisted |
| 143 | Clean installation, “Steam 32-bit · legacy”; Repair Steam files did not run; `No compatible repair source is available` | Missing compatible repair source, separate from Steam64 |
| 149 | Steam64 bootstrap had a `C0000005` / CryptoAPI issue around `advapi32 CryptCreateHash` and provider handle handling | Targeted cryptnet patch developed |
| 150 | Patched `cryptnet.dll`; IPA signed and device-run; Steam fatal-error UI remained; bootstrap log isolated ~60-second manifest download failure | Cryptnet patch did not resolve online-update failure |
| 151 | Built modified `wininet.dll` with bounded `[b151-net]` TCP/TLS diagnostics, package and device tested; 118,418-line log analyzed | TCP/TLS signals captured for *crash-report* WinINet path |
| 152 | Added `[b152-file]` counters to native NTDLL file lookup; iPhoneOS ARM64 archive rebuilt, Xcode Debug build success, debug dylib marker verified, IPA package pass | **Awaiting first on-device install/run and probe analysis** |

Earlier README/IDECK.md mention real login and gameplay on other builds/configurations; **do not assume those acceptance results apply to this Steam64 Build149–152 prefix and branch**.

## 2. Test environment and preservation boundaries

- Target: iPhone 15 Pro Max (physical), iOS 27.0.1 reported for current testing; Xcode 27.2, macOS / Apple Silicon development host.
- Local working tree: `/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck`.
- App project: `app/Madeira.xcodeproj`, scheme `Madeira`, Debug/iPhoneOS.
- Bundle identifier: `com.kimdongup.ideck.build149`; helper: `com.kimdongup.ideck.build149.JITHelper`.
- Apple development signing is host-local; do not commit signing assets or IDs.
- On-device Steam64 prefix: `Documents/wine-steam64` (including user data).
- Build152 output: `/Volumes/Repository/cokacremote/iDeckRuntimeLab/build152-artifacts/iDeck-Build152-Steam64.ipa`.
- **Never delete the installed Build149/150/151 app as a way to “upgrade”; use same-bundle-ID update install.** Deleting it could destroy Steam files, login state, games, and saves. Back up before any risky migration.
- Do not commit Steam executables, CEF resources, credentials, Steam Guard data, pairing files, provisioning assets, private logs or device identifiers. Redact absolute home paths, tokens, network request data and addresses from public artifacts.

## 3. Reproducible artifacts / hashes from reported host output

| Artifact | Hash or evidence | Notes |
|---|---|---|
| `app/Madeira/arm64ec-windows/cryptnet.dll` | SHA-256 `9c26bddebdd0aab63a9576ef25d70441dc817b388abcc639fa2d5c49cdf76346` | Build150 onward cryptnet guard |
| `app/Madeira/arm64ec-windows/wininet.dll` | SHA-256 `7c8e870120377031b28724da45fbd9d358fc31947abe5b554496d5369939772b` | Build151 diagnostic |
| Pre-B152 `libntdll_unix.a` backup | SHA-256 `9f8e8e74de57432ac43b816b5e5b3afcf639e749f1bb994617fe2097d408ea20` | Local `build152-artifacts/libntdll_unix.pre-b152.a` |
| Rebuilt B152 `libntdll_unix.a` | SHA-256 `6a362c6566186faab94711ac39f69bd9c0e4877241b9b9f7c3e6f891f5b90097` | Contains `[b152-file]` string |
| Build151 IPA | SHA-256 `3cb36b1319a1d71dcf20861b9df5b91b972e18cf44c00dcb1828bc517318afaf` | Reported successful signed package |
| Build152 IPA | `BUILD152_IPA_PASS` reported | SHA-256 not provided in this exchange; calculate locally before distribution |

**Provenance caution:** Hashes are user-reported host outputs, not independently downloaded and reverified here. Local binaries are ignored artifacts, not embedded in this Markdown.

## 4. Specific source changes and link chain

### 4.1 Build150 CryptoAPI
- Source patch: `wine/dlls/cryptnet/cryptnet_main.c`, `open_cached_revocation_file()`, provider-acquisition and handle-validity guarding; markers `[b150-cryptnet]`.
- ARM64EC DLL rebuilt by `make -C wine/build-arm64ec dlls/cryptnet/arm64ec-windows/cryptnet.dll -j4`, then staged to `app/Madeira/arm64ec-windows/cryptnet.dll`.
- No longer observed the original identical crash in the Build150 capture, but neither a comprehensive crash-free claim nor a root-cause proof for Steam update follows.

### 4.2 Build151 WinINet
- Modified `wine/dlls/wininet/netconnection.c`; markers `[b151-net]`.
- Instrumented socket start/connect/select/result and Schannel handshake states/certificate result; *diagnostic only*.
- Built `dlls/wininet/arm64ec-windows/wininet.dll`, staged to app payload; hashes matched.
- `[b151-net]` appeared at the later crash-report connection, **not** the earlier initial update socket. This indicates the update flow may use another client/network API or a separate route; do not over-generalize.

### 4.3 Build152 native NTDLL
- Modified `wine/dlls/ntdll/unix/file.c`, `find_file_in_dir()` (code near local source line ~3018) and costly directory-enumeration fallback (~3098).
- Bounded counters: first 32 reports, then every 1024 calls; `[b152-file] find n=... key=... prefix_len=... component_len=... exact=...` and `[b152-file] scan n=... find=... key=...`; hashed path/component fingerprint rather than path strings. **A hash can still correlate repeated access; treat logs as diagnostic data.**
- Local script was `build152-file-probe.py --apply`; source backup of `file.c` was generated. Verify git diff before commits.
- `wine/build-macos/dlls/ntdll/unix/file.o` was successfully built but is **macOS** `LC_BUILD_VERSION platform MACOS`; **never place that object directly into the iPhoneOS archive**.
- Proper iPhoneOS build is `bash build/ntdll-unix/build.sh`: `xcrun -sdk iphoneos clang -arch arm64 -isysroot ... -miphoneos-version-min=17.0`; compiles upstream `file.c` for `build/ntdll-unix/obj/file.o` and archives full `libntdll_unix.a` if all translations succeed. Its script exits on any compilation failure and then copies the archive into `app/Madeira/libntdll_unix.a`.
- Xcode Debug target has `ENABLE_DEBUG_DYLIB=YES`. Final code and `[b152-file]` markers exist in **`Madeira.app/Madeira.debug.dylib`**; absence in `Madeira.app/Madeira` bootstrap executable is **normal**. An earlier packaging script falsely failed because it inspected only the latter. Corrected package validator checks the debug dylib.
- The iOS static archive changed from the pre-B152 SHA-256 to the Build152 SHA-256 above. Build152 Xcode `BUILD SUCCEEDED`, packaging `BUILD152_IPA_PASS`.

### 4.4 Build150–152 relevant local paths / diagnostic inputs
- Original Steam update bootstrap log: on-device `Documents/wine-steam64/drive_c/Program Files (x86)/Steam/logs/bootstrap_log.txt`, where relevant. No complete client/credentials should be copied into GitHub.
- `Documents/madeira-log.txt` is the app diagnostic log. One CoreDevice transfer failed at 5,000,000 of 5,704,550 bytes and produced a **0-byte** local file. Copying to a dedicated fresh folder later succeeded (~10 MB). Do not treat a failed destination or 0-byte file as evidence of missing runtime logs.
- Build151 extraction yielded `TOTAL_LINES=118418`, `B151_EVENTS=4`. The derived `build151-network-timeline.txt` is a summary; source log is more complete but potentially sensitive.

## 5. Event evidence with temporal separation

### 5.1 Initial update request
- Steam thread created: `CHTTPClientThreadPool:0` (Wine tid `0068` reported).
- `[dns] ... "client-update.steamstatic.com" ... after 130 ms (4 result(s))`.
- Immediately afterwards `[srv-conn] ... lport=59643 dport=443 nb=1 ret=-1` then `[srv-conn-done] ... event=OUT err=0 peer=YES`.
- Port-443 success is real but remote endpoint address missing from this trace; **attribution to update host is probable, not conclusive**.
- Steam bootstrap logfile recorded manifest fetch timeout ~60s, `http error 0`; `Steam - Fatal Error` UI subsequently appeared.
- Thread sampling: ~94–95% CPU and call-sites `find_file_in_dir`, `lookup_unix_name` `fstatat`, `getattrlistat`, `openat`, `getdirentries64`. Root cause TBD.

### 5.2 Subsequent crash-report request
- `[dns] ... "crash.steampowered.com" ... after 21 ms (4 result(s))`.
- Separate `lport=59644 dport=443` completed.
- `[b151-net] tcp start family=2 timeout=60000`; `tcp connect result=0 wsa=0`; `tcp connected`; `tls begin compat=0`.
- `secur32.dll` was mapped. `[schannel-ios] process_attach ENTER`; `dlopen(gnutls) ...`; `gnutls_global_init = 0`; `process_attach SUCCESS`.
- No `tls initial status`, no handshake-complete marker in extracted log. Could be delay/hang within credentials initialization or later code path; **not proof of specific TLS function crash**.
- Later separate `0060` `C0000005` exceptions with repeated null reads: investigate independently after initial update path is quantified.

## 6. Immediate handoff: the **next** operator actions

**Do not build Build153 yet; first run Build152.**

1. **Checkpoint**: record `git status --short` at root and in `wine/` and `FEX/`, current commit SHAs, local `file.c` diff, archive/IPAs hashes. The public GitHub `main` may differ from this dirty machine; avoid `git reset --hard`, `git clean -fdx`, submodule updates and copying older libraries over current artifacts.
2. **Install Build152 as update, never delete** current app: use `xcrun devicectl device install app --device <local-device-identifier> <existing-Build152-IPA>`. Confirm `CFBundleIdentifier` unchanged (`com.kimdongup.ideck.build149`) and `CFBundleVersion=152`; run on the device.
3. **Reproduce once**: enable authorized JIT as required, launch Steam64; observe UI timing and whether Steam update manifest is retrieved. Record whether Fatal Error remains; do not assume it will.
4. **Extract logs** to a fresh directory, e.g. `~/Downloads/build152-recovery/madeira-log.txt`, using `xcrun devicectl device copy from --device <local-device-identifier> --domain-type appDataContainer --domain-identifier com.kimdongup.ideck.build149 --source Documents/madeira-log.txt --destination <fresh-file>`. Stop if 0 bytes; do not overwrite the only good log. Collect `bootstrap_log.txt` independently if still relevant.
5. **Analyze probes**: verify `[build] v0.1.3 (152)`, `[b152-file] find` and `scan`. Record last `n` values, `scan/find` ratio, sampled `key` repetition, event timing relative to DNS/connect and Fatal Error, and whether logs predominantly originate from `CHTTPClientThreadPool:0`. Counters alone do not prove thread attribution; use thread IDs or thread name safely.
6. **Decide based on evidence**: if rapidly increasing calls and repeated keys, add targeted call-site/path resolution or caching-performance experiments **behind a reversible flag**, with before/after proof. If counts are modest, prioritize socket/TLS/request telemetry on Steam's *actual* update path and FEX memory-protection error.
7. **Acceptance of next milestone**: Build152 device event capture produced and reviewed, a tightly framed Build153 hypothesis stated, rollback path available; **not** merely another successful compilation.

Useful diagnostic snippets:

```sh
# After a successful on-device run and nonempty log extraction:
grep -m 1 '\[build\]' "$HOME/Downloads/build152-recovery/madeira-log.txt"
grep -F '[b152-file]' "$HOME/Downloads/build152-recovery/madeira-log.txt" | tail -100

# Marker in Debug dylib rather than loader executable:
grep -aF '[b152-file]' \
  /Volumes/Repository/cokacremote/iDeckRuntimeLab/build152-artifacts/DerivedData/Build/Products/Debug-iphoneos/Madeira.app/Madeira.debug.dylib

# Avoid forgotten PATH overrides in zsh:
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"
```

**Note:** Running from a shell with broken `PATH` previously caused false `B152_MARKER_ABSENT` because `grep` did not execute. Never classify probes as absent unless the command itself succeeded.

## 7. Investigation backlog — prioritized, measurable, reversible

| Priority | Work package | Evidence / task | Exit criterion |
|---|---|---|---|
| **P0** | Build152 iPhone acceptance | Update-install, JIT, first Steam64 run; capture native NTDLL probe plus bootstrap and time-series | Build marker, probe hits or explicit verified absence, UI result, preserved prefix |
| **P0** | Thread-to-path attribution | Attach thread id and bounded cost/counter stats; identify whether repeated same-key lookups dominate `CHTTPClientThreadPool:0` | Quantified `find` and `scan` rate per second; repeated-key distribution; cost samples |
| **P1** | Update socket transport trace | Correlate `client-update.steamstatic.com` DNS result with socket peer endpoint; count outbound bytes and inbound bytes, TLS phase and error codes, no payload/token logs | Proof of GET/response or exact stage where progress stops |
| **P1** | FEX code-buffer protection | Audit `Failed to mprotect last page of code buffer`, allocation/protection path, reproduce control; don't confuse host JIT failure with network | Specific failing address/errno/context, regression test, causality experiment |
| **P1** | Case-insensitive lookup optimization | Only after probe data; bound scan or cache *correctly* with invalidation semantics; avoid changes to case resolution correctness | Same-prefix test corpus incl. case variants/rename/non-ASCII/reparse, lower CPU, bootstrap improved or falsifies hypothesis |
| **P2** | Crash-report Schannel path | Trace `ensure_cred_handle`, `AcquireCredentialsHandle`, `InitializeSecurityContextW` return boundaries using narrow/redacted events | Which exact call stalls/fails and status; certificate verification unchanged |
| **P2** | Post-fatal `C0000005` | Symbolicate `0060` exceptions with UUID/dSYM and distinguish primary/secondary | First true faulting frame and independently reproducible trigger |
| **P2** | Operational repeatability | Automate build/IPA verification and log extraction; replace hardcoded temporary paths and ad hoc scripts with checked-in tooling | Two consecutive builds verify bundle, helper, signatures, DLL/archive hashes, Debug dylib |
| **P3** | Product acceptance | Steam update → authentic login → Big Picture → Library → controller → launch test game → return → relaunch/persist | Repeatable >=3 cold-start passes and explicit limitations document |

### Safety / regression rules
- Keep `com.kimdongup.ideck.build149` unchanged for upgrade testing; **never uninstall** until an independently verified backup/migration exists.
- Preserve TLS trust verification and actual Steam authentication/licensing; do **not** disable certificate checking to make the update “work”.
- Avoid wide `WINEDEBUG` or full HTTP payload logging (credential/security and performance risk). Use bounded categorical events.
- Benchmark baseline vs experiment on the *same* Steam prefix snapshot and device mode, with explicit deltas and rollback.
- Never commit build outputs, Steam/CEF binaries, signing profiles, user data, private URLs/tokens or absolute device IDs.
- Avoid conflating the Steam32 legacy Repair source issue (`No compatible repair source is available`) with Steam64 update timeout.

## 8. Estimate of remaining work using the current incremental workflow

**These are planning estimates, not commitments.** No successful Build152 device test has yet been reported. Variance is high because we may discover architectural FEX/Wine incompatibilities after HTTP repair. Assumptions: one knowledgeable engineer; same device and Mac; existing native toolchains/worktree available; work performed in short diagnosis→patch→compile→sign→device→log cycles; no upstream redesign.

| Phase | Engineering effort (person-hours) | Elapsed calendar with 1–3h active work/day | Confidence |
|---|---:|---:|---|
| Build152 install/log triage | 2–5 h | 1–3 days | Medium |
| Identify actual dominant bottleneck and HTTP failure stage | 8–20 h | 1–3 weeks | Low–medium |
| Implement candidate fix + regression/rollback | 12–30 h | 1–4 weeks | Low |
| Successful Steam update/bootstrap on device with repeatability | 8–20 h | 1–3 weeks | Low |
| **Subtotal to repeatable Steam64 bootstrap (non-additive overlap possible)** | **30–75 h** | **~3–8 weeks** | **Low** |
| Login / Big Picture / controller / real game / restarts | additional 30–100+ h | additional ~1–3+ months | Very low |

**Scenarios for Steam64 bootstrap under the present serial workflow:**
- **Optimistic:** 1–2 weeks if Build152 reveals a single, low-risk lookup regression and fixes allow an otherwise functioning HTTP/TLS path.
- **Planning baseline:** **3–8 weeks (30–75 focused engineering hours)** to recover a *repeatable Steam64 bootstrap*; includes multiple device cycles and validation, not full game acceptance.
- **Pessimistic:** **2–4+ months** if the FEX memory subsystem, TLS ABI or Steam64 updater requires nontrivial architecture changes, or if test resources/remote access repeatedly break.

**Full user-facing “Steam64 Big Picture + playable game” milestone:** **~2–6+ months from now** under this serial, incremental troubleshooting approach is a prudent planning allowance; no guarantee. The bootstrap milestone is not equivalent to this end state.

**Why the current process is slow:** repeated host↔device manual copying and 10MB logs; occasional CoreDevice failures; detached source/ignored native artifacts; manual signing/payload checks; instrumenting one hypothesis per release; unknown fundamental compatibility of current Steam version. The long tail is not the C compilation time but waiting on usable evidence and diagnosing interacting Wine/FEX/JIT layers.

**How to shorten the schedule without overstating certainty:**
1. Make a single click/run collection script output a **small scrubbed diagnostic bundle** with build/hash, bootstrap reason, bounded counters and a few relevant thread samples.
2. Include two independent *categorical* probes in one diagnostic release if both are safe and separable (file lookup metrics + socket stage), without simultaneously modifying behavior.
3. Collect same-device baseline/performance budget and use controlled A/B feature flags; discard disproved hypotheses promptly.
4. Push committed source diffs and tool scripts with exact submodule SHAs; keep sensitive/large binaries local; track every build with machine-readable manifest.
5. Assign a clear stop criterion: after ~20 focused hours without narrowing the failure, evaluate alternative updater/network-client strategies and known-good official runtime versions **without bypassing Steam security or licensing**.

## 9. Definition of done / handoff contract

**Current state:** source file patch applied locally, iOS NTDLL compiled, Build152 IPA packaged; **device test pending**. The GitHub handoff document and tracking issue do **not** mean the local Build150–152 patches or generated IPA are on GitHub.

**Next engineer should return:** (a) device build marker; (b) sanitized log counts and timestamps; (c) verified source/submodule SHAs; (d) one evidence-supported causal hypothesis; (e) Build153 plan with rollback and test; (f) updated timeline estimate if the critical path changes.

Avoid declaring Steam64 fixed merely because `BUILD SUCCEEDED`, `BUILD152_IPA_PASS`, DNS, TCP, GnuTLS initialization or a demo on another build succeeded.
