#!/usr/bin/env python3
"""Build122 fail-closed PE32 i386 wevtapi.dll export verifier (read-only)."""
import hashlib
from pathlib import Path
import struct
import sys

REQUIRED = {"EvtQuery", "EvtNext", "EvtRender", "EvtClose", "EvtCreateRenderContext"}

def verify(path):
    data = path.read_bytes()
    def u16(o):
        if o < 0 or o + 2 > len(data): raise ValueError("truncated PE")
        return struct.unpack_from("<H", data, o)[0]
    def u32(o):
        if o < 0 or o + 4 > len(data): raise ValueError("truncated PE")
        return struct.unpack_from("<I", data, o)[0]
    if data[:2] != b"MZ": raise ValueError("DOS header missing")
    nt = u32(0x3c)
    if data[nt:nt+4] != b"PE\0\0": raise ValueError("PE header missing")
    if u16(nt+4) != 0x014c: raise ValueError("not i386 PE")
    sections = u16(nt+6)
    opt_size = u16(nt+20)
    opt = nt+24
    if u16(opt) != 0x10b: raise ValueError("not PE32")
    if opt_size < 112: raise ValueError("PE optional header too short")
    exp_rva = u32(opt+96)
    if not exp_rva: raise ValueError("missing export directory")
    sect_start = opt+opt_size
    size_headers = u32(opt+60)
    def raw(rva):
        if rva < size_headers: return rva
        for i in range(sections):
            o=sect_start+i*40
            virtual_size=u32(o+8)
            virtual_address=u32(o+12)
            raw_size=u32(o+16)
            raw_ptr=u32(o+20)
            if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
                rel=rva-virtual_address
                if rel >= raw_size: raise ValueError("unbacked virtual address")
                return raw_ptr+rel
        raise ValueError("unmapped RVA")
    ed=raw(exp_rva)
    names_count=u32(ed+24)
    names_rva=u32(ed+32)
    if names_count < len(REQUIRED) or names_count > 100000:
        raise ValueError("invalid export count")
    names=[]
    for idx in range(names_count):
        pos=raw(u32(raw(names_rva)+4*idx))
        end=data.find(b"\0",pos,min(len(data),pos+256))
        if end<0: raise ValueError("unterminated export name")
        names.append(data[pos:end].decode("ascii"))
    missing=REQUIRED-set(names)
    if missing: raise ValueError("missing exports: "+", ".join(sorted(missing)))
    print(f"PASS Wine wevtapi PE32/i386 exports: {', '.join(sorted(REQUIRED))}")
    print(f"SHA256: {hashlib.sha256(data).hexdigest()}")
    print(f"File: {path}; bytes={len(data)}")

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("Usage: build122-verify-wevtapi.py PATH")
    try: verify(Path(sys.argv[1]))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise SystemExit("FAIL Build122 wevtapi PE verification: "+str(exc))
