#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see ../../LICENSE-EXCEPTION.md (this file only).
"""Check exact-source patch boundaries and preserve an existing receipt directory."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cef_full_prepare", ROOT / "experiments/cef64-full/prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def main():
    original = Path(sys.argv[1]).read_bytes()
    for size in (256, 512, 1024):
        candidate = prepare.patch_header(original, size)
        # Reversing exactly the two reviewed declarations must restore every
        # byte, including masks, guards, static assertions and licensing.
        restored = candidate
        for name in ("kRegularPoolSize", "kBRPPoolSize"):
            new = f"static constexpr size_t {name} = {size} * 1024 * 1024;".encode()
            assert restored.count(new) == 1
            restored = restored.replace(new, f"static constexpr size_t {name} = kPoolMaxSize;".encode())
        assert restored == original
        try:
            prepare.patch_header(candidate, size)
        except ValueError:
            pass
        else:
            raise AssertionError("Do not silently repatch modified source")
    for data, size in ((original + b"\n", 1024), (original, 768)):
        try:
            prepare.patch_header(data, size)
        except ValueError:
            pass
        else:
            raise AssertionError("Drift or unreviewed geometry accepted")
    with tempfile.TemporaryDirectory(prefix="cef-full-pools-") as temporary:
        root = Path(temporary)
        header = root / "original.h"
        header.write_bytes(original)
        output = root / "receipt"
        output.mkdir()
        sentinel = output / "source-receipt.json"
        sentinel.write_text("preserve-existing-result")
        result = subprocess.run([sys.executable, str(prepare.BASE / "prepare.py"), "--header", str(header),
                                 "--output", str(output)], capture_output=True)
        assert result.returncode and sentinel.read_text() == "preserve-existing-result"
        assert header.read_bytes() == original
    print("PASS: exact-source two-declaration patches, drift rejection, mask/guard preservation and no overwrite")


if __name__ == "__main__":
    main()
