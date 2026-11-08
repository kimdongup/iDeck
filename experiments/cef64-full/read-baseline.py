#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see ../../LICENSE-EXCEPTION.md (this file only).
"""Reproduce metadata from the one observed DLL without executing its code.

This recognizes verified leaf-instruction patterns, not arbitrary candidate DLLs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ideck_pe", BASE.parents[1] / "tools/check-wine-media-dlls.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def read(path):
    image = module.PE(path, machines=(0x8664,))
    baseline = json.loads((BASE / "baseline-contract.json").read_text())
    digest = hashlib.sha256(image.data).hexdigest()
    if digest != baseline["binary_sha256"]:
        raise ValueError("Only the pinned observed DLL is admitted; no inferred decoding of other candidates")
    rva, length = image.directories[0]
    fields = image.unpack("<IIHHIIIIIII", image.offset(rva, 40))
    functions, count, addresses, names, ordinals = fields[6:]
    if not 0 < count <= functions <= 65536:
        raise ValueError("Invalid export count")
    exports = {}
    for i in range(count):
        name = image.name(image.unpack("<I", image.offset(names + 4 * i, 4))[0])
        ordinal = image.unpack("<H", image.offset(ordinals + 2 * i, 2))[0]
        if ordinal >= functions:
            raise ValueError("Invalid export ordinal")
        exports[name] = image.unpack("<I", image.offset(addresses + 4 * ordinal, 4))[0]
    api = exports["cef_api_hash"]
    code = image.data[image.offset(api, 41):image.offset(api, 41) + 41]
    if code[:14] != bytes.fromhex("85c9741a83f902740d83f9017518") or code[38:] != bytes.fromhex("31c0c3"):
        raise ValueError("Unrecognized hash selector")
    hashes = {}
    for name, offset in (("universal", 14), ("commit", 22), ("platform", 30)):
        if code[offset:offset + 3] != b"\x48\x8d\x05" or code[offset + 7] != 0xc3:
            raise ValueError("Unrecognized hash return")
        target = api + offset + 7 + int.from_bytes(code[offset + 3:offset + 7], "little", signed=True)
        value = image.name(target)
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Malformed metadata hash")
        hashes[name] = value
    version = exports["cef_version_info"]
    code = image.data[image.offset(version, 23):image.offset(version, 23) + 23]
    if code[:10] != bytes.fromhex("83f907771289c8488d0d") or code[14:] != bytes.fromhex("486304814801c8ffe0"):
        raise ValueError("Unrecognized version jump table")
    table = version + 14 + int.from_bytes(code[10:14], "little", signed=True)
    values = []
    for i in range(8):
        target = table + image.unpack("<i", image.offset(table + 4 * i, 4))[0]
        if not version <= target < version + 64:
            raise ValueError("Version return outside verified function bounds")
        block = image.data[image.offset(target, 6):image.offset(target, 6) + 6]
        if block[:3] == b"\x31\xc0\xc3":
            values.append(0)
        elif block[0] == 0xb8 and block[5] == 0xc3:
            values.append(int.from_bytes(block[1:5], "little"))
        else:
            raise ValueError("Unrecognized version return")
    return dict(binary_sha256=digest, api_hashes=hashes, version_info=values,
                exports=sorted(exports), runtime_execution=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dll", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = read(args.dll)
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print("Pinned CEF metadata reproduced without executing the DLL")
