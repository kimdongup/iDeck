# Full CEF small-pool control

This directory prepares a full-source CEF memory experiment. It is **not** a
validated replacement for Steam's libcef. Own tooling is GPL-3.0-or-later with
the Madeira Converter Exception; patched Chromium/CEF sources retain BSD notices.

## Compatibility gate

`baseline-contract.json` records metadata read from the exact observed Steam
libcef, SHA-256 `c85bf94462b3c79baeac63823db52d15e116eead71ea414e5d3a112c59e434d3`.
Its CEF commit string is `bbb75964a9f4095daf2926163a63cbf11af56565` and Chromium
version is126.0.6478.183. The public CEF revision used for the old chrome_elf-only
build is `a5d51ba9db7ee74a523dc247bd09ec91ba4d7446`.

| C API hash | Observed Steam DLL | Public-source control |
|---|---|---|
| Windows | `97314fe45c14007fca596262a64cad69467df21f` | `0d99d1b9b85b2efab91a39d6fc325bb6d56fd524` |
| Universal | `908f7378d71977393cee4bc349055b7365c3673c` | `ed1dfa5ff8a041241f8fb72eb7454811f358f0d3` |

These are different public C API contracts. Do not change returned hashes to
pretend that structures/callbacks match. The source origin of the observed
commit is unresolved: upstream GitHub commit lookup returned422; the guessed
ValveSoftware/cef repository returned404. This is not proof no source exists.

The public source can be used as a **control** for reservation behavior. Matching
Chromium version, exports or even API hashes does not establish full Steam ABI,
resource-pack or runtime compatibility.

## Prepare a candidate

Use a fresh **full** CEF checkout with ordinary production build files. The old
focused chrome_elf checkout intentionally discarded libcef's build graph and
must not be reused. The pins are in `public-control.json`; its CEF
`CHROMIUM_BUILD_COMPATIBILITY.txt` selects Chromium126.0.6478.183 and
depot_tools `fca881606e`.

The official pinned `cef/tools/automate/automate-git.py` accepts `--branch=6478`,
`--checkout=a5d51ba9db7ee74a523dc247bd09ec91ba4d7446`, `--no-build`, and
`--no-distrib`. Use a new disposable download directory; it downloads a large
Chromium dependency tree. Full Windows compilation needs an installed supported
Visual Studio C++ toolchain/Windows SDK and adequate RAM/disk. The current8 GiB
Mac is not a validated Windows build host. No complete checkout has been synced
by this experiment.

Emit a patch without changing the input header:

```sh
python3 prepare.py --header /path/to/original/partition_address_space.h --output /new/receipt-dir
```

Apply to an already synchronized full source tree:

```sh
python3 prepare.py --checkout /path/to/chromium/src --output /new/receipt-dir
```

The default changes exactly the regular/BRP declarations to1 GiB each, matching
the existing source chrome_elf pool size. Masks remain derived from these
constants; BRP guards, assertions, maximum-capacity metadata and failure paths
are preserved. `--pool-mib 512` and256 are separate unbuilt candidates. A changed
source hash, focused build graph or existing result directory is rejected.

Applying this common header in the full tree affects all allocator copies
compiled from it, including libcef and chrome_elf. It does not mean all CEF/V8
reservations are controlled by these two constants. Native Wine backing and
distinct pool ownership still require device validation.

## Windows build handoff — not executed here

After preparing that full tree, use the pinned CEF project's original hook and
targets, rather than the old component builder. In an existing configured
Windows/depot_tools environment, from `chromium/src`:

```powershell
$env:DEPOT_TOOLS_WIN_TOOLCHAIN = "0"
$env:GN_DEFINES = 'is_official_build=false is_component_build=false symbol_level=1'
$env:GN_OUT_CONFIGS = 'Release_GN_x64'
python cef/tools/gclient_hook.py
ninja -C out/Release_GN_x64 libcef chrome_elf -j 2
```

These are prospective commands checked against pinned source, not a successful
Windows run. Preserve the actual `args.gn`, source/patch hashes, compiler and SDK
versions, complete build log and all runtime resource outputs from the same
build. Do not copy only libcef into an unrelated resource bundle. Recheck the
patched header hash after the hook, because official patch application can
modify the checkout.

## Candidate validation

`contract-probe.c` uses normal LoadLibrary initialization followed by the two
public metadata APIs. It must run only on a disposable test Windows host with
the candidate's runtime dependencies. It does not disable DllMain, suppress
assertions or fake allocation success. Cross-compiling this small probe is
separate from compiling libcef.

```sh
x86_64-w64-mingw32-clang -std=c11 -Wall -Wextra -Werror -O2 -municode contract-probe.c -o cef-contract-probe.exe
```

Run with an absolute candidate DLL path and an external timeout. Exit2 means
load failure,3 missing/malformed metadata,4 baseline metadata mismatch,0 metadata
match. The known public-source control is expected to fail the baseline hash
gate. Exit0 still does not certify export closure, C++ layouts, pak/V8 resources,
BrowserReady, login or repeated starts. The source receipt deliberately records
`compiled=false` and `replacement_eligible=false`; never relabel it as a DLL test.
