#!/usr/bin/env python3
"""Iteratively compile and stage Wine ARM64 PE import dependencies, with a bounded closure gate."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',required=True)
    ap.add_argument('--arch',default='aarch64-windows')
    ap.add_argument('--jobs',type=int,default=2)
    ap.add_argument('--max-rounds',type=int,default=12)
    args=ap.parse_args()
    root=Path(args.root).resolve()
    stage=root/'app/Madeira'/args.arch
    modpath=Path(__file__).with_name('wine-pe-closure.py')
    spec=importlib.util.spec_from_file_location('pe_closure',modpath)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for round_no in range(1,args.max_rounds+1):
        report=mod.audit(root,args.arch,[])
        if report['invalid_or_wrong_arch']:
            raise SystemExit('Invalid PE architecture/format: '+repr(report['invalid_or_wrong_arch']))
        missing=sorted(report['missing'])
        print('ROUND',round_no,'modules',report['scanned'],'missing',len(missing),flush=True)
        if not missing:
            print('PASS: staged PE static import closure')
            return
        targets=[]
        for name in missing:
            if not name.endswith(('.dll','.drv','.exe')):
                raise SystemExit('Unknown PE module extension: '+name)
            source=root/'wine/build-bootstrap-pe/dlls'/(name if name.endswith('.drv') else name.rsplit('.',1)[0])/args.arch/name
            if not (root/'wine/dlls'/(name if name.endswith('.drv') else name.rsplit('.',1)[0])/'Makefile.in').is_file():
                raise SystemExit('No Wine build definition for '+name)
            targets.append('dlls/'+(name if name.endswith('.drv') else name.rsplit('.',1)[0])+'/'+args.arch+'/'+name)
        cmd=['make','-C',str(root/'wine/build-bootstrap-pe'),'-j'+str(args.jobs),*targets]
        print('BUILD',*missing,flush=True)
        subprocess.run(cmd,check=True)
        for name in missing:
            src=root/'wine/build-bootstrap-pe/dlls'/(name if name.endswith('.drv') else name.rsplit('.',1)[0])/args.arch/name
            if not src.is_file(): raise SystemExit('Build target missing: '+str(src))
            machine,_=mod.imports(src)
            expected={'aarch64-windows':0xaa64,'i386-windows':0x14c}[args.arch]
            if machine!=expected: raise SystemExit(name+' wrong PE machine')
            shutil.copy2(src,stage/name)
    raise SystemExit('Closure did not converge in max rounds')
if __name__=='__main__': main()
