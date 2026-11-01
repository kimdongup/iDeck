#!/usr/bin/env python3
"""Offline PE import closure audit; standard library only, no Wine source modification."""
import argparse
from collections import deque
import json
from pathlib import Path
import struct

SYSTEM = {'api-ms-win-core','api-ms-win-crt','ext-ms-win','kernel32.dll'}  # kernel32 checked if present; other API sets contracted
def imports(path):
    b = path.read_bytes()
    def u16(o): return struct.unpack_from('<H',b,o)[0]
    def u32(o): return struct.unpack_from('<I',b,o)[0]
    if len(b)<256 or b[:2]!=b'MZ': raise ValueError('not PE')
    pe=u32(0x3c)
    if b[pe:pe+4]!=b'PE\x00\x00': raise ValueError('bad PE signature')
    machine=u16(pe+4); n=u16(pe+6); opt=pe+24
    magic=u16(opt)
    if magic not in (0x20b,0x10b): raise ValueError('bad optional header')
    dd=opt+(112 if magic==0x20b else 96)
    sec=opt+u16(pe+20)
    sections=[]
    for j in range(n):
        q=sec+j*40
        vsize,vaddr,size,raw=struct.unpack_from('<IIII',b,q+8)
        sections.append((vaddr,vaddr+max(vsize,size),raw,size))
    def off(rva):
        for start,end,raw,size in sections:
            if start<=rva<end and rva-start<size:
                return raw+rva-start
        raise ValueError('RVA outside file: '+hex(rva))
    def cstr(o):
        end=b.find(b'\x00',o,min(len(b),o+512))
        if end<0: raise ValueError('unterminated DLL name')
        return b[o:end].decode('ascii','replace').lower()
    names=set()
    # import directory, delay import directory
    for directory,entry_size in ((1,20),(13,32)):
        rva,length=struct.unpack_from('<II',b,dd+directory*8)
        if not rva or not length: continue
        base=off(rva)
        for i in range(min(2048,max(1,length//entry_size))):
            at=base+i*entry_size
            if at+entry_size>len(b): break
            if not any(b[at:at+entry_size]): break
            if directory==1: name_rva=u32(at+12)
            else:
                flags=u32(at); name_rva=u32(at+4)
                if not (flags&1): continue
            try: names.add(cstr(off(name_rva)))
            except (ValueError,IndexError): pass
    return machine,sorted(names)

def audit(root, arch, targets):
    root=Path(root)
    stage=root/'app/Madeira'/arch
    build=root/'wine/build-bootstrap-pe/dlls'
    available={p.name.lower():p for p in stage.glob('*.dll')}
    lookup=lambda dll: build/dll.removesuffix('.dll')/arch/dll
    visited=set(); missing={}; edges={}; mismatch={}
    todo=deque(targets or sorted(available))
    while todo:
        name=todo.popleft().lower()
        if name in visited: continue
        visited.add(name)
        if name.startswith(('api-ms-win-','ext-ms-win-')): continue
        local=available.get(name)
        if local is None:
            candidate=lookup(name)
            missing[name]={'build_exists':candidate.is_file(),'imported_by':[]}
            if not candidate.is_file(): continue
            local=candidate
        try: machine,deps=imports(local)
        except Exception as e:
            mismatch[name]=str(e);continue
        expected={'aarch64-windows':0xaa64,'i386-windows':0x14c}.get(arch)
        if expected and machine!=expected: mismatch[name]=f'wrong machine {hex(machine)}'
        edges[name]=deps
        todo.extend(deps)
    for parent,deps in edges.items():
        for name in deps:
            if name in missing: missing[name]['imported_by'].append(parent)
    return {'arch':arch,'scanned':len(edges),'missing':missing,'invalid_or_wrong_arch':mismatch,'dependency_graph':edges}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--root',required=True)
    a.add_argument('--arch',default='aarch64-windows',choices=['aarch64-windows','i386-windows'])
    a.add_argument('--target',action='append',default=[])
    a.add_argument('--require-runtime',action='append',default=[],help='DLL observed in device dynamic LoadLibrary/search logs')
    a.add_argument('--json')
    a.add_argument('--strict',action='store_true')
    args=a.parse_args()
    report=audit(args.root,args.arch,args.target)
    stage=Path(args.root)/'app/Madeira'/args.arch
    for dll in args.require_runtime:
        name=dll.lower()
        if not name.endswith('.dll'): name+='.dll'
        if not (stage/name).is_file():
            report['missing'].setdefault(name, {'build_exists':(Path(args.root)/'wine/build-bootstrap-pe/dlls'/name[:-4]/args.arch/name).is_file(),'imported_by':['runtime-observed']})
    print('PE dependency closure',args.arch,'scanned',report['scanned'])
    for name,info in sorted(report['missing'].items()):
        print('MISSING',name,'build_artifact='+str(info['build_exists']),'required_by='+','.join(info['imported_by'][:8]))
    for name,issue in sorted(report['invalid_or_wrong_arch'].items()):
        print('INVALID',name,issue)
    if args.json: Path(args.json).write_text(json.dumps(report,indent=2)+'\n')
    if args.strict and (report['missing'] or report['invalid_or_wrong_arch']): raise SystemExit(2)
if __name__=='__main__': main()
