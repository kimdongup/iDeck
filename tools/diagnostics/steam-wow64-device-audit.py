#!/usr/bin/env python3
"""Read-only iDeck Build100 WoW64 diagnosis of existing iPhone logs.
Runs on the user's Mac with Xcode devicectl. No app changes, no writes to device,
no Steam login contents printed, no device identifiers printed. Temporary raw
log copies are automatically deleted after sanitized categorical aggregation.
"""
# Example: IDECK_BUNDLE_ID=com.example.ideck IDECK_IPA=/path/to/app.ipa python3 tools/diagnostics/steam-wow64-device-audit.py
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BUNDLE = os.environ.get("IDECK_BUNDLE_ID", "com.kimdongup.ideck.build100")
FILES = ("madeira-log.txt", "madeira-log.prev.txt")
IPA_PATH = os.environ.get("IDECK_IPA", "").strip()
IPA = Path(IPA_PATH).expanduser() if IPA_PATH else None
REQUIRED_PE = ("aarch64-windows/ntdll.dll", "aarch64-windows/wow64.dll", "aarch64-windows/wow64win.dll", "aarch64-windows/cmd.exe", "aarch64-windows/explorer.exe", "i386-windows/ntdll.dll", "i386-windows/kernel32.dll", "i386-windows/user32.dll")
PATTERNS = {
    "steam_launch_requested": r"\[steam-ui\] experiment-begin",
    "wine_process_started": r"Wine process thread launched",
    "wineserver_started": r"Wineserver thread launched successfully",
    "wine_process_start_failure": r"Failed to start Wine process|Wineserver not running!",
    "wine_main_pe_probe": r"\[WineProc\] PE probe:",
    "bootstrap_ntdll_begin": r"\[wine-bootstrap\] stage=ntdll state=begin",
    "bootstrap_ntdll_ok": r"\[wine-bootstrap\] stage=ntdll state=ok",
    "bootstrap_wow64_begin": r"\[wine-bootstrap\] stage=wow64-ntdll state=begin",
    "bootstrap_wow64_ok": r"\[wine-bootstrap\] stage=wow64-ntdll state=ok",
    "bootstrap_apiset_begin": r"\[wine-bootstrap\] stage=apiset state=begin",
    "bootstrap_apiset_ok": r"\[wine-bootstrap\] stage=apiset state=ok",
    "bootstrap_server_init_ok": r"\[wine-bootstrap\] stage=server-init-done state=ok",
    "wine_main_returned": r"\[WineProc\] __wine_main returned normally",
    "wine_main_exited": r"\[WineProc\] Wine exited with code",
    "wine_child_thread_entry": r"\[Wine child thread\] ENTRY:",
    "cmd_child_thread_entry": r"\[Wine child thread\] ENTRY:.*(?:^|[/\\])cmd\.exe",
    "steam_child_thread_entry": r"\[Wine child thread\] ENTRY:.*(?:^|[/\\])steam\.exe",
    "control_child_thread_entry": r"\[Wine child thread\] ENTRY:.*(?:^|[/\\])ideck-control\.exe",
    "steam_process_start": r"\[steam-ui-process\] event=start kind=steam",
    "steam_process_end": r"\[steam-ui-process\] event=end kind=steam",
    "services_process_start": r"\[steam-ui-process\] event=start kind=services",
    "steam_exe_spawn_legacy_marker": r"\[phase\] spawn:.*steam\.exe",
    "wow_guest_reserve_refused": r"\[wow-window\] refused: map too small",
    "wow_guest_no_aligned_slot": r"no free 4GB-aligned slot",
    "wow_guest_boot_failed": r"BOOT FAILED.*guest-window-reserve|guest window reserve returned",
    "wow_status_no_memory": r"\bc0000017\b",
    "early_hold_created": r"\[wow-early\] held B=",
    "early_hold_skipped": r"\[wow-early\] skipped:",
    "early_hold_imported": r"\[wow-early\] imported pre-JIT",
    "early_hold_rejected": r"\[wow-early\] import REJECTED",
    "placeholder_reserved": r"\[wow-window\] placeholder reserved",
    "placeholder_adopted": r"\[wow-window\] adopted placeholder",
    "guest_window_reserved": r"\[wow-window\] reserved B=",
    "steam_ui_milestone": r"\[steam-ui\].*(browser-ready|cef-initialization)",
    "steam_ui_observation_ended": r"\[steam-ui\] observation-ended",
    "wine_builtin_dll_load_failure": r"failed to load .*?(?:ntdll|dll)|failed to load .*?error [0-9a-f]{4,8}|c0000135|STATUS_DLL_NOT_FOUND",
    "wine_fatal": r"fatal.error|assertion.failed|\bSIGSEGV\b|\bSIGABRT\b|EXC_BAD_ACCESS",
    "wine_ntdll_mentioned": r"ntdll\.dll|load_ntdll",
    "wine_loader_image_issue": r"cannot find|could not load|invalid.*PE|missing.*DLL",
}
CHRONOLOGY = [
    ("steam-launch-requested", r"\[steam-ui\] experiment-begin"),
    ("wineserver-started", r"Wineserver thread launched successfully"),
    ("wine-process-started", r"Wine process thread launched"),
    ("pe-probe", r"\[WineProc\] PE probe:"),
    ("bootstrap", r"\[wine-bootstrap\] stage=(?:ntdll|wow64-ntdll|apiset|server-init-done) state=(?:begin|ok)"),
    ("wow-placeholder-reserved", r"\[wow-window\] placeholder reserved"),
    ("wow-placeholder-adopted", r"\[wow-window\] adopted placeholder"),
    ("wine-child-entry", r"\[Wine child thread\] ENTRY:"),
    ("cmd-child-entry", r"\[Wine child thread\] ENTRY:.*cmd\.exe"),
    ("steam-child-entry", r"\[Wine child thread\] ENTRY:.*steam\.exe"),
    ("control-child-entry", r"\[Wine child thread\] ENTRY:.*ideck-control\.exe"),
    ("steam-process-started", r"\[steam-ui-process\] event=start kind=steam"),
    ("child-boot-failed", r"\[child-boot-fail\]|\[Wine child\] BOOT FAILED"),
    ("wine-main-ended", r"\[WineProc\] (__wine_main returned normally|Wine exited with code)"),
    ("steam-ui-observation-ended", r"\[steam-ui\] observation-ended"),
    ("wine-loader-failed", r"failed to load .*?(?:ntdll|dll)|failed to load .*?error [0-9a-f]{4,8}|c0000135|STATUS_DLL_NOT_FOUND"),
    ("wine-loader-fatal", r"fatal.error|assertion.failed|\bSIGSEGV\b|\bSIGABRT\b|EXC_BAD_ACCESS"),
]

def command(argv, timeout=90):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)

def choose_device(info):
    available = []
    for d in (info.get("result") or {}).get("devices") or []:
        if not isinstance(d, dict):
            continue
        props = d.get("properties") or {}
        connection = d.get("connectionProperties") or props.get("connection") or {}
        hw = d.get("hardwareProperties") or props.get("hardware") or {}
        sw = d.get("deviceProperties") or props.get("software") or {}
        name = str(sw.get("name") or "")
        model = str(hw.get("marketingName") or hw.get("productType") or "")
        kind = str(hw.get("deviceType") or "")
        platform = str(hw.get("platform") or "")
        transport = str(connection.get("transportType") or "").lower()
        pairing = str(connection.get("pairingState") or d.get("state") or "").lower()
        identifier = str(d.get("identifier") or "")
        if not identifier or "iphone" not in (kind + model + name).lower():
            continue
        if platform and platform.lower() not in ("ios", "iphoneos"):
            continue
        if "simulator" in model.lower() or "unpaired" in pairing or "unavailable" in pairing:
            continue
        available.append((identifier, transport))
    explicit = os.environ.get("BUILD100_DEVICE_ID", "").strip()
    if explicit:
        matching = [x for x in available if x[0] == explicit]
    else:
        wired = [x for x in available if x[1] in ("wired", "usb")]
        matching = wired or available
    if len(matching) != 1:
        raise RuntimeError(
            "Expected one paired physical iPhone (prefer wired). "
            "Set BUILD100_DEVICE_ID to its full devicectl identifier if ambiguous."
        )
    return matching[0][0]

def summarize(name, content):
    lines = content.splitlines()
    print(f"\n=== {name} ({len(lines)} lines; redacted aggregates only) ===")
    for title, pattern in PATTERNS.items():
        print(f"{title}: {sum(bool(re.search(pattern, line, re.I)) for line in lines)}")
    free = []
    for line in lines:
        if "[wow-window] refused: map too small" in line:
            m = re.search(r"\((\d+) MB free VA", line)
            if m and len(free) < 8:
                free.append(int(m.group(1)))
    print(f"guest_window_refusal_free_mb_samples: {free}")
    print("Milestone chronology (matching line numbers; never raw device log text):")
    found = []
    for idx, line in enumerate(lines, 1):
        for label, regex in CHRONOLOGY:
            if re.search(regex, line, re.I):
                found.append((idx, label))
    for idx, label in found[-45:]:
        print(f"  line={idx} event={label}")
    if not found:
        print("  NO_RECOGNIZED_MILESTONES")

    stages = []
    for line in lines:
        if "[wow-va] stage=" not in line:
            continue
        stage = re.search(r"\bstage=([a-z0-9-]+)", line, re.I)
        free_mb = re.search(r"\bfree_mb=(\d+)", line)
        largest_mb = re.search(r"\blargest_mb=(\d+)", line)
        slots = re.search(r"\baligned_slots=(\d+)", line)
        regions = re.search(r"\bregions=(\d+)", line)
        complete = re.search(r"\bcomplete=([01])", line)
        if stage and free_mb and largest_mb and slots and regions and complete:
            stages.append((stage.group(1), int(free_mb.group(1)),
                           int(largest_mb.group(1)), int(slots.group(1)),
                           int(regions.group(1)), int(complete.group(1))))
    print("VA census: stage | scanned_free_MB | largest_MB | aligned_slots | regions | complete")
    for item in stages[:30]:
        print("  " + " | ".join(map(str, item)))
    if not stages:
        print("  NO_RETRIEVED_CENSUS_EVENTS")
    if any(item[-1] == 0 for item in stages):
        print("NOTE: complete=0 measurements are PARTIAL scans, not total free VA.")
    if any(item[-1] == 0 and item[-2] >= 100000 for item in stages):
        print("SCAN_CAP: 100000 regions reached; this instrument cannot report whole-map free VA.")


def audit_ipa():
    print("\nOffline IPA Wine PE resource audit (bundled files only):")
    if IPA is None:
        print("  IPA audit skipped (set IDECK_IPA to an IPA file)")
        return
    if not IPA.is_file():
        print("  IPA NOT FOUND locally; bundled resource status unverified")
        return
    try:
        with zipfile.ZipFile(IPA) as archive:
            paths = set(archive.namelist())
            for relative in REQUIRED_PE:
                name = "Payload/Madeira.app/" + relative
                status = "PRESENT" if name in paths else "MISSING"
                print(f"  {relative}: {status}")
    except (OSError, zipfile.BadZipFile):
        print("  IPA NOT READABLE; audit unavailable")

def main():
    if sys.platform != "darwin":
        raise RuntimeError("Run this script in macOS Terminal, not inside the Linux container.")
    with tempfile.TemporaryDirectory(prefix="ideck-build100-wow-") as folder:
        working = Path(folder)
        devices_json = working / "devices.json"
        r = command(["xcrun", "devicectl", "list", "devices", "--json-output", str(devices_json)])
        if r.returncode:
            raise RuntimeError("Xcode devicectl device listing failed; check USB, trust, and unlock.")
        target = choose_device(json.loads(devices_json.read_text(encoding="utf-8")))
        print("Selected one connected physical iPhone (identifier redacted).")
        print(f"Reading existing logs from {BUNDLE}; no new launch requested.")
        found = 0
        for name in FILES:
            dest = working / name
            copied = command([
                "xcrun", "devicectl", "device", "copy", "from",
                "--device", target, "--domain-type", "appDataContainer",
                "--domain-identifier", BUNDLE,
                "--source", f"Documents/{name}", "--destination", str(dest)
            ], timeout=100)
            if copied.returncode != 0 or not dest.is_file():
                print(f"{name}: NOT RETRIEVED (missing or unreadable; no crash inference)")
                continue
            found += 1
            summarize(name, dest.read_text(encoding="utf-8", errors="replace"))
        print("\nPrepared guest boot files (existence only; no content printed):")
        for name in ("madeira-steam-ui.cmd", "ideck-control.exe"):
            dest = working / ("prepared-" + name)
            copied = command([
                "xcrun", "devicectl", "device", "copy", "from",
                "--device", target, "--domain-type", "appDataContainer",
                "--domain-identifier", BUNDLE,
                "--source", "Documents/wine/drive_c/" + name,
                "--destination", str(dest)
            ], timeout=90)
            if copied.returncode == 0 and dest.is_file():
                print(f"{name}: PRESENT ({dest.stat().st_size} bytes)")
            else:
                print(f"{name}: NOT RETRIEVED (missing or unreadable)")
        if not found:
            print("\nNo readable device logs. Verify app container selection; "
                  "CoreDevice 7000 alone is not proof of a PE failure.")
        audit_ipa()
        print("\nDone. Temporary copies deleted. No iPhone data changed.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("DIAGNOSTIC BLOCKED:", exc, file=sys.stderr)
        sys.exit(1)
