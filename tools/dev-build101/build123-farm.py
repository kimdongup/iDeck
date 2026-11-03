#!/usr/bin/env python3
"""Build 123: checkpointed Wine i386 DLL farm; protect existing iDeck binaries.

audit: read-only; build: Darwin-only make batches into persistent stage;
install: fail-closed before copying staged PE files into app/Madeira/i386-windows.

Does NOT build graphics DLLs: those are produced by build123-dxmt-on-mac.sh.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

SUFFIXES = ("dll", "drv", "cpl", "acm", "ax", "ocx")
REQUIRED = {
    "wtsapi32.dll": {"WTSFreeMemory", "WTSQuerySessionInformationW",
                     "WTSRegisterSessionNotification", "WTSUnRegisterSessionNotification"},
    "powrprof.dll": {"CallNtPowerInformation", "PowerDeterminePlatformRoleEx"},
    "wevtapi.dll": {"EvtQuery", "EvtNext", "EvtRender", "EvtClose", "EvtCreateRenderContext"},
    "dxgi.dll": {"CreateDXGIFactory1"},
}
# DXMT owns graphics; do not stage Wine/wined3d's DXGI or D3D libraries.
GRAPHICS = {"dxgi.dll", "d3d11.dll", "d3d10core.dll", "winemetal.dll",
            "d3d9.dll", "d3d9shim.dll", "d3d9-emulated.dll",
            "wined3d.dll"}
# The iOS host cannot provide the Unix/display or kernel components below.
EXCLUDE = set("""
winevulkan.dll vulkan-1.dll opencl.dll wpcap.dll wineps.drv winemac.drv
ir50_32.dll wow32.dll vga.dll hal.dll w32skrnl.dll
wow64.dll wow64win.dll wow64cpu.dll xtajit.dll xtajit64.dll
winebth.sys winebus.sys winehid.sys
""".split()) | GRAPHICS
# Never replace previously verified executable/loader/bootstrap or unrelated
# existing farm binaries. New files are introduced additively.
PROTECTED = {"ntdll.dll", "kernel32.dll", "kernelbase.dll", "win32u.dll",
             "apisetschema.dll", "bcryptprimitives.dll", "wevtapi.dll"}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(1024 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def pe_info(path):
    """Fail closed for PE32 i386, optionally resolve export names."""
    b = path.read_bytes()
    if len(b) < 128 or b[:2] != b"MZ":
        raise ValueError("not a PE image")
    def u16(o):
        if o < 0 or o + 2 > len(b): raise ValueError("truncated PE")
        return struct.unpack_from("<H", b, o)[0]
    def u32(o):
        if o < 0 or o + 4 > len(b): raise ValueError("truncated PE")
        return struct.unpack_from("<I", b, o)[0]
    nt = u32(0x3c)
    if b[nt:nt+4] != b"PE\0\0" or u16(nt+4) != 0x14c:
        raise ValueError("wrong PE signature or Machine (expected i386)")
    opt = nt + 24
    if u16(opt) != 0x10b: raise ValueError("expected PE32 optional header")
    count = u16(nt+6)
    if count > 128: raise ValueError("invalid section count")
    hdrsz = u32(opt+60)
    sect = opt + u16(nt+20)
    def offset(rva):
        if rva < hdrsz: return rva
        for i in range(count):
            o = sect + i * 40
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", b, o+8)
            if va <= rva < va+max(vsize, rawsize):
                if rva-va >= rawsize: raise ValueError("RVA lacks file backing")
                return rawptr+rva-va
        raise ValueError("unmapped PE RVA")
    names = set()
    exp = u32(opt+96)
    if exp:
        e = offset(exp)
        num = u32(e+24)
        if num > 150000: raise ValueError("implausible export count")
        name_table = offset(u32(e+32))
        for i in range(num):
            pos = offset(u32(name_table+4*i))
            end = b.find(b"\0", pos, min(pos+256, len(b)))
            if end < 0: raise ValueError("unterminated export")
            names.add(b[pos:end].decode("ascii"))
    return {"bytes":len(b), "sha256":hashlib.sha256(b).hexdigest(),
            "machine":"014c", "exports":names}


def targets(makefile):
    # Captures explicit Wine PE rules, rather than trusting a handwritten list.
    p = re.compile(r"^(dlls/[^/\s:]+/i386-windows/[^/\s:]+\.(" +
                   "|".join(SUFFIXES) + r")):", re.M)
    text = makefile.read_text(errors="replace")
    all_targets = sorted({m.group(1) for m in p.finditer(text)})
    result = []
    skipped = []
    for name in all_targets:
        filename = Path(name).name.lower()
        if filename in EXCLUDE:
            skipped.append({"target":name,"reason":"iOS-unsupported or DXMT-owned"})
        else:
            result.append(name)
    return result, skipped


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n")
    os.replace(tmp, path)


def options():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["audit","build","install","verify"])
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--out", type=Path)
    p.add_argument("--app-dir", type=Path, help="verify files in this Madeira.app, not source farm")
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--max-targets", type=int, default=0,
                   help="diagnostic dry run only; blocks install if used")
    return p.parse_args()


def main():
    a = options()
    root=a.root.resolve()
    work = a.out or (root.parent/"build123-artifacts"/"farm")
    stage = work/"i386-windows"
    dest = (a.app_dir/"i386-windows") if a.mode == "verify" and a.app_dir else root/"app/Madeira/i386-windows"
    tree = root/"wine/build-bootstrap-pe"
    makefile = tree/"Makefile"
    if not makefile.is_file() or not dest.is_dir():
        raise SystemExit("Missing configured Wine bootstrap Makefile or i386 app resource directory")
    all_targets, skipped = targets(makefile)
    if not all_targets: raise SystemExit("No i386 target rules discovered")
    seen_files = {}
    for item in all_targets:
        name=Path(item).name.lower()
        if name in seen_files and seen_files[name]!=item:
            raise SystemExit("Ambiguous Wine DLL output name: "+name+
                             " from "+seen_files[name]+" and "+item)
        seen_files[name]=item
    installed = {p.name.lower() for p in dest.iterdir() if p.is_file()}
    staged = {p.name.lower() for p in stage.iterdir() if p.is_file()} if stage.exists() else set()
    pending = [x for x in all_targets
               if Path(x).name.lower() not in installed | staged]
    print(f"Build123 farm: targets={len(all_targets)}, excluded={len(skipped)}, "
          f"installed={len(installed)}, staged={len(staged)}, pending={len(pending)}",flush=True)
    missing = sorted(k for k in REQUIRED if k not in installed | staged)
    print("Required still absent:", ", ".join(missing) or "none",flush=True)
    if a.mode == "audit":
        print("DXMT build.ninja:", (root/"dxmt/build-pe-i386/build.ninja").exists())
        print("Output stage:",stage)
        return

    if a.mode == "build":
        if sys.platform != "darwin":
            raise SystemExit("Build requires macOS/Xcode; Linux may run --audit / --verify only")
        if not (1 <= a.jobs <= 4 and 1 <= a.batch <= 64):
            raise SystemExit("jobs must be 1..4 and batch must be 1..64")
        compiler = root/"toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
        if not (compiler/"i686-w64-mingw32-clang").exists():
            raise SystemExit("Pinned i686 llvm-mingw compiler is absent")
        shutil.disk_usage(root)
        if shutil.disk_usage(root).free < 20*1024**3:
            raise SystemExit("Need >=20GiB on external build volume to begin full Wine farm")
        env=os.environ.copy()
        env["PATH"]=str(compiler)+os.pathsep+env.get("PATH","")
        stage.mkdir(parents=True, exist_ok=True)
        logs=work/"logs";logs.mkdir(parents=True,exist_ok=True)
        failures={}
        success={}
        # --max-targets never allows install; used only to validate the farm
        # in batches on the user's Mac.
        subset = pending[:a.max_targets] if a.max_targets else pending
        # Fail-closed checkpoint, even if the previous run was complete.
        save_json(work/"wine-farm-progress.json",
                  {"mode":"building","total_targets":len(all_targets),
                   "batch_total":len(subset),"batch_done":0,
                   "skipped":skipped,"successful":{},"failures":{}})
        for start in range(0,len(subset),a.batch):
            batch=subset[start:start+a.batch]
            logfile=logs/f"batch-{start//a.batch:04d}.log"
            print(f"[{start+1}-{start+len(batch)}/{len(subset)}] make -j{a.jobs}",flush=True)
            with logfile.open("w") as log:
                command=["make","-C",str(tree),"-k",f"-j{a.jobs}",*batch]
                proc=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            for target in batch:
                source=tree/target
                name=source.name.lower()
                if not source.is_file():
                    failures[name]={"target":target,"reason":"make did not produce file","log":str(logfile)}
                    continue
                try:
                    info=pe_info(source)
                except (OSError,ValueError,UnicodeDecodeError,struct.error) as exc:
                    failures[name]={"target":target,"reason":str(exc),"log":str(logfile)}
                    continue
                dest_stage=stage/name
                tmp=dest_stage.with_name(name+".tmp")
                shutil.copy2(source,tmp)
                os.replace(tmp,dest_stage)
                success[name]={"target":target,"sha256":info["sha256"],"bytes":info["bytes"]}
            save_json(work/"wine-farm-progress.json",
                      {"mode":"building","total_targets":len(all_targets),
                       "batch_done":start+len(batch),"batch_total":len(subset),
                       "skipped":skipped,"successful":success,"failures":failures})
            print(f"  batch rc={proc.returncode}; staged={len(success)} failed={len(failures)}",flush=True)
        save_json(work/"wine-farm-progress.json",
                  {"mode":"complete" if not a.max_targets else "partial",
                   "total_targets":len(all_targets),"skipped":skipped,
                   "successful":success,"failures":failures})
        required_wine=("wtsapi32.dll","powrprof.dll","wevtapi.dll")
        for name in required_wine:
            f=(stage/name) if (stage/name).is_file() else (dest/name)
            if not f.is_file(): raise SystemExit(f"Build123 required Wine DLL failed: {name}")
            have=pe_info(f)["exports"]
            if not REQUIRED[name].issubset(have):
                raise SystemExit(f"Build123 {name} missing required exports: {REQUIRED[name]-have}")
        print(f"Wine farm staged; optional failures={len(failures)}; "
              "run DXMT step and install gate next.",flush=True)
        return

    if a.mode == "install":
        if sys.platform != "darwin":
            raise SystemExit("Installation into iOS app resource farm requires macOS")
        manifest=work/"wine-farm-progress.json"
        if not manifest.exists() or json.loads(manifest.read_text()).get("mode")!="complete":
            raise SystemExit("Full farm not completed; refusing to install partial candidates")
        for name, exports in REQUIRED.items():
            f=(stage/name) if (stage/name).is_file() else (dest/name)
            if not f.is_file():
                raise SystemExit(f"Missing required i386 DLL: {name}")
            info=pe_info(f)
            if not exports.issubset(info["exports"]):
                raise SystemExit(f"Missing exports in {name}: {sorted(exports-info['exports'])}")
        new_files=[]
        conflicts=[]
        for p in stage.iterdir():
            if not p.is_file() or p.name.endswith((".tmp",".build123-tmp")):
                continue
            existing=dest/p.name
            if existing.exists():
                if sha(existing)!=sha(p):
                    conflicts.append(p.name)
                continue
            info=pe_info(p)
            new_files.append((p, info["sha256"]))
        # If a graphic DLL already exists but is from a different version,
        # refuse silent substitution. Require an explicit separate review.
        if any(n in GRAPHICS for n in conflicts):
            raise SystemExit("DXMT variant conflict: "+",".join(conflicts))
        print(f"Installing {len(new_files)} missing modules; preserving "
              f"{len(installed)} existing modules; non-graphic duplicates={len(conflicts)}")
        for p,digest in new_files:
            out=dest/p.name
            tmp=dest/(p.name+".build123-tmp")
            shutil.copy2(p,tmp)
            if sha(tmp)!=digest: raise SystemExit(f"copy mismatch: {p}")
            if out.exists(): tmp.unlink(); continue
            os.replace(tmp,out)
        save_json(work/"farm-installed.json",
                  {"new_count":len(new_files),"new_sha256":{p.name:h for p,h in new_files},
                   "preserved_count":len(installed),"duplicates":conflicts,
                   "required":sorted(REQUIRED)})
        print("PASS Build123 validated compatible Wine + DXMT farm staged into app resources")
        return

    if a.mode == "verify":
        for name, exports in REQUIRED.items():
            f=dest/name
            if not f.is_file(): raise SystemExit(f"Required i386 module missing: {name}")
            have=pe_info(f)["exports"]
            if not exports.issubset(have):
                raise SystemExit(f"Wrong exports {name}: {sorted(exports-have)}")
        installed_manifest=work/"farm-installed.json"
        if installed_manifest.is_file():
            manifest=json.loads(installed_manifest.read_text())
            for name,digest in manifest.get("new_sha256",{}).items():
                p=dest/name
                if not p.is_file() or sha(p)!=digest:
                    raise SystemExit(f"Build123 farm mismatch in app: {name}")
            print("PASS Build123 farm manifest SHA-256 verified",
                  len(manifest.get("new_sha256",{})), "files")
        print("PASS required i386 CEF delay-load dependency exports (including DXMT)")
        return


if __name__=="__main__":
    main()
