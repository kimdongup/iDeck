# Build 99 — 32-bit Steam guest-window reservation diagnosis

## Observed failure (user's iPhone 15 Pro Max / iOS 27.0.1)

Original log:
- `[phase] spawn:L"C:\\Steam32BundleLab\\steam.exe"`
- `[wow-window] refused: map too small (539 MB free VA; a window needs 4096 MB plus MADEIRA_WOW_MIN_FREE_GB=8 left over)`
- `[Wine child] BOOT FAILED at stage 'guest-window-reserve' ... 0xc0000017`

The Wine server and JIT started; the i386 child failed before the Steam GUI or CEF could start. This is virtual-address *layout* exhaustion, not a physical RAM or storage capacity claim.

## Source root cause

`ContentView.startSteamUIExperiment` runs `explorer.exe` (64-bit), then starts the 32-bit Steam client as a child. The default guest window is allocated lazily in `build/ntdll-unix/virtual_ios.c:ios_wow_window_reserve`. When the child spawns, all but 539 MB of kernel-reported free virtual address space is gone, so a 4 GB window is no longer possible.

The existing opt-in `MADEIRA_WOW_PLACEHOLDERS=1` calls `ios_wow_reserve_placeholders` in `ios_wow_session_start` at the end of `virtual_init` — before initial Wine PE loading. The pseudo-process later **adopts** the already-reserved slot without needing to reserve 4 GB afresh. This was verified in `tests/host/check-lazy-windows.py`.

## Source patch (working branch: fix/wow64-guest-window-availability)

`app/Madeira/ContentView.swift`, `runWineFullSequence(steamUI:)`: default `MADEIRA_WOW_PLACEHOLDERS=1` for Steam UI launches only, before JIT pool allocation and Wine init, and allow `madeira.cfg` `env.MADEIRA_WOW_PLACEHOLDERS = 0` to disable for A/B. Normal game launches are unchanged.

New regression test: `tests/host/check-steam-wow-placeholder.py`.

## Fastest test — NO SOURCE REBUILD

The shipped Build 99 code already implements this *opt-in* mode. The original, installed Build 99 should be able to test the same native mechanism using the Files app:

1. iPhone Files > On My iPhone > iDeck > `madeira.cfg` (iDeck Documents directory). Alternatively use the supported app file-sharing path.
2. Append exactly one line (do NOT overwrite other settings):
   ```
   env.MADEIRA_WOW_PLACEHOLDERS = 1
   ```
3. Fully quit iDeck, relaunch, enable JIT, and run Steam Big Picture.
4. Check log for `[madeira-env]` export, `[wow-window] placeholder reserved` at startup, then `[wow-window] adopted placeholder` at the Steam 32-bit child spawn.
5. If the old `refused: map too small` is gone, capture the NEXT failure stage or successful Steam view. If early reservation is itself refused, capture `[wow-window] refused` lines from startup; the app may need a different layout. Do NOT set `MADEIRA_WOW_MIN_FREE_GB=0` just to bypass the guard.
6. To A/B restore original behaviour, set `env.MADEIRA_WOW_PLACEHOLDERS = 0` and fully relaunch. A restarted process is required; existing mappings are not released by changing the file mid-session.

This opt-in might reserve a large virtual window early and impact other apps or native allocations. It is not a guarantee of Steam success; use logs to decide. Sideloadly signing/Personal Team Extended VA restrictions are orthogonal.

## Validation

- PASS: `python3 tests/host/check-lazy-windows.py` (real virtual_ios.c policy under mocked Mach VM)
- PASS: `python3 tests/host/check-small-va-band.py`
- PASS: `python3 tests/host/check-steam-wow-placeholder.py` (Steam Swift launch integration static checks)
- `tests/host/check-steam-ui.py` unavailable on Linux: `swiftc` not installed
- Cannot Xcode-build or install on iPhone in the Linux container, and the public snapshot excludes some built runtime payloads

No upstream commit or push performed; all changes are local to `/shared/iDeckRuntimeLab/iDeck`.
