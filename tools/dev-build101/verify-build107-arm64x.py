#!/usr/bin/env python3
"""Check the ARM64X Wine ntdll PE and its ARM64EC metadata before packaging."""
import pathlib
import struct
import sys


def check(path: pathlib.Path) -> None:
    data = path.read_bytes()
    def u16(o): return struct.unpack_from("<H", data, o)[0]
    def u32(o): return struct.unpack_from("<I", data, o)[0]
    def u64(o): return struct.unpack_from("<Q", data, o)[0]

    if len(data) < 1024 or data[:2] != b"MZ":
        raise ValueError("missing MZ header or unexpectedly short file")
    pe = u32(0x3c)
    if pe + 264 >= len(data) or data[pe:pe+4] != b"PE\0\0":
        raise ValueError("missing or truncated PE header")
    machine = u16(pe+4)
    if machine != 0xaa64:
        raise ValueError(f"expected ARM64X native machine 0xaa64, got {machine:#x}")
    opt = pe+24
    if u16(opt) != 0x20b:
        raise ValueError("expected PE32+")
    size_opt = u16(pe+20)
    nsections = u16(pe+6)
    if size_opt < 112+11*8:
        raise ValueError("optional header lacks load config directory")
    image_base = u64(opt+24)
    image_size = u32(opt+56)
    data_dirs = opt+112
    cfg_rva,cfg_size = struct.unpack_from("<II",data,data_dirs+10*8)
    def rva_to_off(rva):
        first=pe+24+size_opt
        for i in range(nsections):
            s=first+i*40
            if s+40>len(data): raise ValueError("truncated section table")
            vsize,va,rsize,roff=struct.unpack_from("<IIII",data,s+8)
            if va<=rva<va+max(vsize,rsize):
                off=roff+rva-va
                if off<len(data): return off
        raise ValueError(f"unmapped RVA {rva:#x}")
    if cfg_size < 0xd0 or not cfg_rva:
        raise ValueError("ARM64X load configuration missing or too small")
    cfg_off=rva_to_off(cfg_rva)
    if cfg_off+0xd0>len(data): raise ValueError("truncated load config")
    chpe_ptr=u64(cfg_off+0xc8)
    if not image_base<=chpe_ptr<image_base+image_size:
        raise ValueError(f"CHPE metadata VA absent or outside image: {chpe_ptr:#x}")
    metadata_off=rva_to_off(chpe_ptr-image_base)
    # ARM64EC metadata begins with a nonzero version and mapped region.
    version=u32(metadata_off)
    if version==0 or version>100:
        raise ValueError(f"unexpected CHPE metadata version: {version}")
    print(f"PASS ARM64X PE machine={machine:#x} bytes={len(data)} "
          f"CHPE_VA={chpe_ptr:#x} version={version} path={path}")


if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("Usage: verify-build107-arm64x.py PATH/ntdll.dll")
    try: check(pathlib.Path(sys.argv[1]))
    except (OSError,ValueError,struct.error) as e: raise SystemExit(f"FAIL ARM64X: {e}")
