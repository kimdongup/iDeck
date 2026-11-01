# Build 100 → Build 101: WoW64 startup diagnosis

## Ground truth (iPhone, Build 100)
- JIT confirmed; Steam UI launch requested once; wineserver and Wine process started.
- Initial WoW64 4GB placeholder reserved once, with no **observed** placeholder adoption or 32-bit Steam process start.
- No `STATUS_NO_MEMORY`, guest window refusal, or explicit loader fatal in the captured sanitized log. This is different from upstream Issue #3's observed guest-window-reserve failure.
- The VA census at `app-pre-jit` was complete (171 mapped regions). After JIT, every census was partial with `regions=100000 complete=0`. These values **cannot** be interpreted as the total available VA.
- `madeira-steam-ui.cmd` and `ideck-control.exe` were present in the installed app's guest C: drive.

## Build 100 IPA resource audit
The inspected IPA contained `aarch64-windows/cmd.exe`, `aarch64-windows/explorer.exe`, and `i386-windows/ntdll.dll`. It lacked `aarch64-windows/ntdll.dll`, `aarch64-windows/wow64.dll`, `aarch64-windows/wow64win.dll`, `i386-windows/kernel32.dll`, and `i386-windows/user32.dll` at those bundle locations. Absence at those paths is **not by itself proof** of a specific first failure: inspect loader fallbacks and any alternate module farm.

## Changes on this branch
1. `tools/diagnostics/steam-wow64-device-audit.py`: read-only retrieval of already written logs, sanitized startup milestones, optional IPA file audit via `IDECK_IPA=/path/to/file.ipa`, configurable `IDECK_BUNDLE_ID`.
2. `tools/diagnostics/test_steam_wow64_device_audit.py`: offline unit tests for event classification, wired-device selection, and IPA file inventory.
3. `build/ntdll-unix/loader_ios.c`: categorical `[wine-bootstrap]` begin/ok events around NTDLL, WoW64 NTDLL, API-set loading, and server init.

## Test and follow-up
Run from this repository:

```bash
python3 -m unittest discover -s tools/diagnostics -p 'test_steam_wow64_device_audit.py' -v
```

On the Mac attached to the iPhone, run the diagnostic script against an **already executed** and installed build:

```bash
IDECK_IPA=/path/to/actual.ipa python3 tools/diagnostics/steam-wow64-device-audit.py
```

The new loader markers require a rebuilt and installed IPA; they cannot appear in old Build 100 logs. Audit and build a matched native/PE Wine component set before declaring a functional Build 101. Do not disable VA guard checks, overwrite live mappings, or copy credential-bearing raw logs to public GitHub.

## Workspace caution
The external SSD previously reported < 1GB free, and the separate local `fix/wow64-guest-window-availability` checkout has numerous uncommitted source changes and modified submodules. Preserve it, perform any builds on a volume with ample free capacity, and integrate selectively after review. No iPhone installation was performed by these GitHub-only changes.
