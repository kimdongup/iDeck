#!/usr/bin/env python3
"""Regression tests for Build123 farm parsing, PE validation, and safety gates."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SPEC=importlib.util.spec_from_file_location("build123_farm",HERE/"build123-farm.py")
farm=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(farm)


class FarmTests(unittest.TestCase):
    def test_real_wevtapi_exports_and_machine(self):
        p=ROOT/"app/Madeira/i386-windows/wevtapi.dll"
        if not p.is_file():
            self.skipTest("Existing Build122 DLL not available")
        inf=farm.pe_info(p)
        self.assertEqual(inf["machine"],"014c")
        self.assertTrue(farm.REQUIRED["wevtapi.dll"].issubset(inf["exports"]))

    def test_reject_wrong_arch_and_corrupt_pe(self):
        p=ROOT/"app/Madeira/i386-windows/wevtapi.dll"
        if not p.is_file(): self.skipTest("No sample")
        data=bytearray(p.read_bytes())
        nt=struct.unpack_from("<I",data,0x3c)[0]
        struct.pack_into("<H",data,nt+4,0xaa64)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"bad.dll"
            dest.write_bytes(data)
            with self.assertRaisesRegex(ValueError,"Machine"):
                farm.pe_info(dest)
            dest.write_bytes(b"not-a-pe")
            with self.assertRaisesRegex(ValueError,"PE"):
                farm.pe_info(dest)

    def test_targets_exclude_wined3d_graphics(self):
        make=ROOT/"wine/build-bootstrap-pe/Makefile"
        if not make.is_file(): self.skipTest("No Wine build tree")
        targets,skips=farm.targets(make)
        self.assertIn("dlls/wtsapi32/i386-windows/wtsapi32.dll",targets)
        self.assertIn("dlls/powrprof/i386-windows/powrprof.dll",targets)
        self.assertNotIn("dlls/dxgi/i386-windows/dxgi.dll",targets)
        self.assertNotIn("dlls/wined3d/i386-windows/wined3d.dll", targets)
        self.assertTrue(any("dxgi.dll" in item["target"] for item in skips))
        self.assertTrue(any("wined3d.dll" in item["target"] for item in skips))

    def test_audit_does_not_create_stage(self):
        with tempfile.TemporaryDirectory() as t:
            stage=Path(t)/"new-audit-stage"
            x=subprocess.run(["python3",str(HERE/"build123-farm.py"),"audit",
                              "--root",str(ROOT),"--out",str(stage)],
                              text=True,capture_output=True)
            self.assertEqual(x.returncode,0,x.stderr)
            self.assertFalse(stage.exists())
            self.assertIn("pending=",x.stdout)

    def test_verify_refuses_missing_mandatory(self):
        # The Build122 source farm is intentionally missing WTSAPI32.
        p=ROOT/"app/Madeira/i386-windows/wtsapi32.dll"
        if p.exists(): self.skipTest("Source farm has already been upgraded")
        x=subprocess.run(["python3",str(HERE/"build123-farm.py"),"verify",
                          "--root",str(ROOT)],text=True,capture_output=True)
        self.assertNotEqual(x.returncode,0)
        self.assertIn("Required i386 module missing",x.stderr+x.stdout)


if __name__=="__main__":
    unittest.main()
