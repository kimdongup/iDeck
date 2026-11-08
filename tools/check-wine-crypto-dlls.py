#!/usr/bin/env python3
"""Check real ARM64EC CryptoAPI providers and packaged import closure.

This is a static packaging check. Device acquire/hash/random tests remain
necessary; implemented export addresses do not establish runtime correctness.
"""
import importlib.util
import argparse
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "wine_media_pe", Path(__file__).with_name("check-wine-media-dlls.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PE = module.PE

REQUIRED = (
    "CPAcquireContext", "CPCreateHash", "CPDecrypt", "CPDeriveKey",
    "CPDestroyHash", "CPDestroyKey", "CPEncrypt", "CPExportKey", "CPGenKey",
    "CPGenRandom", "CPGetHashParam", "CPGetKeyParam", "CPGetProvParam",
    "CPGetUserKey", "CPHashData", "CPHashSessionKey", "CPImportKey",
    "CPReleaseContext", "CPSetHashParam", "CPSetKeyParam", "CPSetProvParam",
    "CPSignHash", "CPVerifySignature",
)


def check(farm, extra_roots=()):
    farm = Path(farm)
    shipped = {p.name.lower(): p for p in farm.iterdir() if p.is_file()}
    providers = ("rsaenh.dll", "dssenh.dll")
    extra_roots = tuple(name.lower() for name in extra_roots)
    for name in extra_roots:
        if name not in shipped:
            raise ValueError("missing additional root module " + name)
    for name in providers:
        if name not in shipped:
            raise ValueError("missing ARM64EC provider " + name)
        pe = PE(shipped[name])
        header = struct.unpack_from("<I", pe.data, 0x3c)[0]
        machine = struct.unpack_from("<H", pe.data, header + 4)[0]
        if machine == 0x8664:
            # Wine's hybrid PE uses AMD64 in the raw COFF header. LLVM identifies
            # ARM64EC through its CHPE load configuration and native code map.
            optional = header + 24
            image_base = pe.unpack("<Q", optional + 24)[0]
            config_rva, config_size = pe.directories[10]
            if not config_rva or config_size < 208:
                raise ValueError(name + ": missing ARM64EC load configuration")
            config = pe.offset(config_rva, 208)
            metadata = pe.unpack("<Q", config + 200)[0] - image_base
            version, code_map, count = pe.unpack("<III", pe.offset(metadata, 12))
            if version != 2 or not 0 < count <= 65536:
                raise ValueError(name + ": unsupported ARM64EC CHPE code map")
            ranges = [pe.unpack("<II", pe.offset(code_map + i * 8, 8)) for i in range(count)]
            native = [(rva & ~3, size) for rva, size in ranges if rva & 3 == 1 and size]
            if not native:
                raise ValueError(name + ": no ARM64EC code range")
            for rva, size in native:
                pe.offset(rva, size)
        elif machine not in (0xa641, 0xa64e):
            raise ValueError(name + ": expected ARM64EC/ARM64X provider")
        exports = pe.exports()
        missing = [x for x in REQUIRED if not exports.get(x)]
        if missing:
            raise ValueError(name + ": missing implemented exports " + ", ".join(missing))
        if pe.imports(True):
            raise ValueError(name + ": unexpected ARM64EC delay imports")

    visited, pending = set(), list(providers) + list(extra_roots)
    missing = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        try:
            # Madeira's ntdll bridge is a native ARM64 DLL in the hybrid farm.
            pe = PE(shipped[name], machines=(0x8664, 0xa641, 0xa64e, 0xaa64))
        except ValueError as error:
            raise ValueError(name + ": " + str(error)) from error
        for dep in pe.imports() | pe.imports(True) | pe.forwarded_modules():
            if dep in shipped:
                pending.append(dep)
            elif dep.startswith(("api-ms-", "ext-ms-")) and "apisetschema.dll" in shipped:
                # Contract presence only; export forwarding is outside this check.
                continue
            else:
                missing.add(name + " -> " + dep)
    if missing:
        raise ValueError("missing import modules: " + ", ".join(sorted(missing)))
    print("Crypto providers: ARM64EC implemented CP exports; "
          + str(len(visited)) + " modules in static import closure; runtime unverified")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("farm")
        parser.add_argument("--root", action="append", default=[], help="Additional DLL import/forwarder root")
        args = parser.parse_args()
        check(args.farm, args.root)
    except (OSError, ValueError, UnicodeError, struct.error) as error:
        sys.exit("Wine crypto DLL check failed: " + str(error))
