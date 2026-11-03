#!/usr/bin/env python3
"""Identify PE32 delayed import DLLs from FEX exception stack return RVAs.

The return RVA points immediately after __delayLoadHelper2's 5-byte call,
which follows a 5-byte push descriptor VA.

Read-only; no global decompiler.
"""
import argparse
import hashlib
import struct
import zipfile
from pathlib import Path


def describe(pe: bytes, rva: int, ipa_names: set[str]):
    if pe[:2] != b"MZ":
        raise ValueError("not an MZ/PE file")
    nt = struct.unpack_from("<I", pe, 0x3c)[0]
    if pe[nt:nt+4] != b"PE\0\0":
        raise ValueError("not a PE file")
    if struct.unpack_from("<H", pe, nt+4)[0] != 0x14c:
        raise ValueError("not PE32/i386")
    opt=nt+24
    imagebase=struct.unpack_from("<I",pe,opt+28)[0]
    sections=struct.unpack_from("<H",pe,nt+6)[0]
    sect_off=opt+struct.unpack_from("<H",pe,nt+20)[0]
    def loc(rva):
        for i in range(sections):
            sh=sect_off+40*i
            _,sec_rva,rawsize,ptr=struct.unpack_from("<IIII",pe,sh+8)
            if sec_rva<=rva<sec_rva+rawsize:
                return ptr+(rva-sec_rva)
        raise ValueError(f"RVA not backed by PE section: {rva:#x}")
    def string(rva):
        o=loc(rva)
        end=pe.find(b"\0",o,min(o+256,len(pe)))
        if end<0:raise ValueError("unterminated import string")
        return pe[o:end].decode("ascii")
    before=loc(rva-10)
    if pe[before]!=0x68 or pe[loc(rva-5)]!=0xe8:
        raise ValueError("return RVA not an expected delay-load stub")
    desc_va=struct.unpack_from("<I",pe,before+1)[0]
    attr,name,hmod,iat,iat_names,*_=struct.unpack_from("<8I",pe,loc(desc_va-imagebase))
    if attr!=1: raise ValueError(f"unknown descriptor attributes {attr:#x}")
    dll=string(name)
    exports=[]
    for j in range(256):
        ptr=struct.unpack_from("<I",pe,loc(iat_names+4*j))[0]
        if ptr==0: break
        if ptr&0x80000000: exports.append(f"#{ptr&0xffff}")
        else: exports.append(string(ptr+2))
    result={"rva":hex(rva),"descriptor":hex(desc_va),"dll":dll,"imports":exports}
    if ipa_names is not None: result["ipa_i386_present"]=dll.lower() in ipa_names
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pe",type=Path)
    ap.add_argument("rvas", nargs="+", help="return RVAs, e.g. 0x972b2ef")
    ap.add_argument("--ipa",type=Path)
    a=ap.parse_args()
    pe=a.pe.read_bytes()
    print("Input", a.pe, "SHA256", hashlib.sha256(pe).hexdigest())
    names=None
    if a.ipa:
        with zipfile.ZipFile(a.ipa) as z:
            names={name.split("/")[-1].lower() for name in z.namelist()
                   if "/i386-windows/" in name and not name.endswith("/")}
        print("IPA",a.ipa)
    for value in a.rvas:
        try:
            out=describe(pe,int(value,0),names)
            print(f"RETURN {out['rva']}: {out['dll']} descriptor={out['descriptor']}"
                  + (f" ipa_i386_present={out['ipa_i386_present']}" if names is not None else ""))
            print("  imports:",", ".join(out["imports"]))
        except (ValueError,IndexError,struct.error,UnicodeDecodeError) as e:
            print(f"RETURN {value}: cannot resolve: {e}")


if __name__=="__main__":
    main()
