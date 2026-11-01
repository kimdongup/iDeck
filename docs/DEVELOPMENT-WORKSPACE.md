# iDeck canonical workspace and storage map

## Canonical source repository

- **Mac:** `/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck`
- **Linux workmachine:** `/shared/iDeckRuntimeLab/iDeck`
- **Git repository:** `kimdongup/iDeck` (fork). Keep `kuscholar/iDeck` as `upstream` for comparison only.
- **Build 101 active tools:** `tools/dev-build101/`
- **Device diagnostics:** `tools/diagnostics/`
- **WoW64 engineering notes and tests:** `docs/`, `tests/host/`.

The two OS paths above point at the same host-mounted source folder. Do not clone iDeck
again elsewhere to work on Build 101. Work in the existing checkout; do not move
its entire source tree after creating compiled iOS toolchains and build caches.

## Non-source artifacts

`/Volumes/Repository/cokacremote/iDeckRuntimeLab/build100-artifacts/` and
`build101-artifacts/` contain generated builds, toolchains, backups, and
signed test output, and should **not** be committed. Existing diagnostic logs
stay in `iDeckRuntimeLab/diagnostics/` (not in public Git).

Legacy paths directly under `iDeckRuntimeLab/` for the five active build
scripts are compatibility symlinks targeting `iDeck/tools/dev-build101/`.
Run them at their original names or directly from the canonical repository.

`/shared/iDeckSigningOnly` is a separate signing workspace, not a second
Git iDeck source checkout; preserve its provisioning/signing content.

## Git semantics

- The main source checkout is one Git root; FEX, wine, dxmt and madeira-dock
  are pinned Git submodules, **not separate iDeck forks**.
- Existing uncommitted Build 100 experiments were branched from `006e05d`
  instead of rewriting the fork's `main`, which has diverged.
- Only upload reviewed source, documentation and tests. Avoid IPA, binaries,
  credentials, provisioning profiles, logs containing personal/device data,
  FEX AI-generated contributions, and build caches.
- All source changes should be made in the canonical folder, then reflected in
  a named GitHub feature branch. Keep `main` unchanged until review.

## Linux / Mac storage accuracy

Container mount evidence:

```text
/       overlay (Docker Desktop Linux container disk)
/tmp    same overlay as /
/shared /run/host_mark/Volumes[/Repository/cokacremote] (fakeowner)
```

Docker's `df -h /shared` may reflect the host file-sharing facade rather than
the actual macOS APFS volume capacity. For definitive size on the Mac:

```bash
df -h /System/Volumes/Data /Volumes/Repository
diskutil info /Volumes/Repository | grep -E 'Device Identifier|Volume Total Space|Volume Free Space|Container Free Space'
```

When the macOS command output is available, distinguish internal Docker.raw
physical usage from external APFS file usage; the container's `df -h /` reports
the Linux filesystem, not the macOS volume where Docker.raw is stored.

## Container cleanup

On 2026-11-01, 424 entries at the top of `/tmp` older than seven days were
removed, excluding live/runtime paths. The overlay filesystem's displayed
available space rose from approximately 159 GiB to 184 GiB. The action did not
modify the external /shared source tree. The audit manifest lives outside Git
at `iDeckRuntimeLab/diagnostics/container-tmp-cleanup-2026-11-01.json`.
