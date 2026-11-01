#!/usr/bin/env python3
"""Host-only tests; no device connection or Xcode required."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).with_name("steam-wow64-device-audit.py")
spec = importlib.util.spec_from_file_location("steam_wow64_device_audit", SOURCE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeviceAuditTests(unittest.TestCase):
    def test_wow_reservation_not_misreported_as_steam(self):
        log = (
            "[steam-ui] experiment-begin genuine\n"
            "[wow-window] placeholder reserved B=0x0000000400000000\n"
            "[wow-va] stage=post-fex-arena map_end=0x001000000000 free_mb=523 "
            "largest_mb=213 aligned_slots=0 regions=100000 complete=0\n"
            "[steam-ui] observation-ended running=0 seconds=120\n"
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.summarize("synthetic", log)
        text = out.getvalue()
        self.assertIn("placeholder_reserved: 1", text)
        self.assertIn("placeholder_adopted: 0", text)
        self.assertIn("steam_process_start: 0", text)
        self.assertIn("SCAN_CAP: 100000", text)

    def test_real_steam_child_detected(self):
        log = (
            "[steam-ui-process] event=start kind=steam slot=1 machine=014c\n"
            "[Wine child thread] ENTRY: fd=3, argc=2, exe=C:\\Steam\\steam.exe\n"
            "[wow-window] adopted placeholder B=0x100000000\n"
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.summarize("synthetic", log)
        text = out.getvalue()
        self.assertIn("steam_process_start: 1", text)
        self.assertIn("steam_child_thread_entry: 1", text)
        self.assertIn("placeholder_adopted: 1", text)

    def test_bootstrap_trace(self):
        text = "[wine-bootstrap] stage=ntdll state=begin\\n[wine-bootstrap] stage=ntdll state=ok\\n"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.summarize("synthetic", text)
        self.assertIn("bootstrap_ntdll_begin: 1", out.getvalue())
        self.assertIn("bootstrap_ntdll_ok: 1", out.getvalue())

    def test_loader_error_count(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.summarize("synthetic", "failed to load /not-real/ntdll.dll error c0000135\n")
        self.assertIn("wine_builtin_dll_load_failure: 1", out.getvalue())

    def test_device_prefers_wired_iphone(self):
        def device(identifier, name, transport):
            return {"identifier": identifier,
                    "hardwareProperties": {"deviceType": "iPhone", "platform": "iOS"},
                    "deviceProperties": {"name": name},
                    "connectionProperties": {"transportType": transport,
                                             "pairingState": "paired"}}
        result = {"result": {"devices": [device("a", "iPhone A", "network"),
                                          device("b", "iPhone B", "wired")]}}
        self.assertEqual(module.choose_device(result), "b")

    def test_ipa_resource_audit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ipa"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Payload/Madeira.app/aarch64-windows/ntdll.dll", b"test")
            prev = module.IPA
            module.IPA = path
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    module.audit_ipa()
                self.assertIn("aarch64-windows/ntdll.dll: PRESENT", out.getvalue())
                self.assertIn("aarch64-windows/wow64.dll: MISSING", out.getvalue())
            finally:
                module.IPA = prev


if __name__ == "__main__":
    unittest.main()
