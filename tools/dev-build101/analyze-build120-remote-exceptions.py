#!/usr/bin/env python3
"""Read-only chronology and module correlation for Build120 Steam CEF exceptions.

Usage:
  python3 tools/dev-build101/analyze-build120-remote-exceptions.py \
      ~/Downloads/ideck-build107-device-20261101-184351

The remote-exception32 event is emitted by NtReadVirtualMemory while
Crashpad reads another process's exception record; it does NOT itself
identify the faulting process or prove a fresh machine exception.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

SECTION = re.compile(r"\[iOS-xins\].*?\s(?P<name>[^\s]+)\ssec=0x(?P<start>[a-fA-F0-9]+)-0x(?P<end>[a-fA-F0-9]+)")
MODULE = re.compile(r"\bLoad module (?P<name>[^ ]+) \([^)]*\): (?P<base>[0-9A-Fa-f]+)")
REMOTE = re.compile(r"\[steam-ui-remote-exception32\] code=0x(?P<code>[0-9a-fA-F]+) guest_pc=0x(?P<pc>[0-9a-fA-F]+)")
WINDOW = re.compile(r"\bB=0x(?P<base>[0-9a-fA-F]+) \(guest window")
BREAK = re.compile(r"\[task-exc\] BREAKPOINT|\[int3-guest\] guest_rip=|\[steam-ui-remote-exception32\]")
CONTEXT = re.compile(r"\[build120-cef-|\[steam-ui-process\] event=(?:start|end)|\[build109-pe-loader\].*failed|\[build110-import-fail\]")

@dataclass(frozen=True)
class Section:
    line: int
    name: str
    start: int
    end: int
    tag: str

def parse(path: Path) -> None:
    print(f"=== {path} ===")
    if not path.is_file():
        print("File unavailable"); return
    lines = path.read_text(errors="replace").splitlines()
    sections: list[Section] = []
    bases: list[tuple[int, str, int, str]] = []
    windows: set[int] = set()
    remote: list[tuple[int, int, int]] = []
    relevant: list[tuple[int, str]] = []
    counts = Counter()
    for n, line in enumerate(lines, 1):
        m = SECTION.search(line)
        tag = line.split(" ", 2)[1] if line.startswith(("D ", "E ")) and len(line.split(" ", 2)) > 1 else "?"
        if m:
            sections.append(Section(n,m["name"],int(m["start"],16),int(m["end"],16),tag))
        m = MODULE.search(line)
        if m:
            bases.append((n,m["name"],int(m["base"],16),tag))
        m = WINDOW.search(line)
        if m:
            windows.add(int(m["base"],16))
        m = REMOTE.search(line)
        if m:
            remote.append((n,int(m["code"],16),int(m["pc"],16)))
        if "[build120-cef-" in line: counts["build120-probes"] += 1
        if "[int3-guest] guest_rip=" in line: counts["guest-int3"] += 1
        if "[task-exc] BREAKPOINT" in line: counts["host-breakpoint"] += 1
        if "Load module bcryptprimitives.dll" in line: counts["bcryptprimitives-loaded"] += 1
        if "[steam-ui-process] event=end kind=cef" in line: counts["cef-ended"] += 1
        if CONTEXT.search(line):
            relevant.append((n,line.strip()))
    print("Lines:",len(lines))
    print("Signals:",", ".join(f"{key}={counts[key]}" for key in
        ("bcryptprimitives-loaded","build120-probes","guest-int3","host-breakpoint","cef-ended")))
    print("Remote exception records:",len(remote))
    print("Observed WoW windows:",", ".join(hex(w) for w in sorted(windows)) or "(not logged)")
    print("Last relevant lifecycle/probe events:")
    for n,text in relevant[-12:]:
        print(f"  {n}: {text[:220]}")
    if not remote:
        print("No remote exception32 records in this file.")
        return
    for n,code,pc in remote[-6:]:
        print(f"\nREMOTE-EXCEPTION line {n}: code=0x{code:08x} guest_pc=0x{pc:08x}")
        print("  Note: this is a Crashpad-style remote record read, NOT necessarily an exception raised at this log line.")
        # A 32-bit PE guest PC is an offset inside a process-specific WoW window.
        candidate_windows = sorted(windows) if windows else [
            0x7100000000,0x7200000000,0x7300000000,0x7400000000]
        hits: list[tuple[int,Section]]=[]
        for wb in candidate_windows:
            host_pc=wb+pc
            for sec in sections:
                if sec.line <= n and sec.start <= host_pc < sec.end:
                    hits.append((wb,sec))
        # Keep newest section per (window, module, process tag) as a hint only.
        seen=set()
        if hits:
            print("  EXACT segment-range candidates (may include other processes):")
            for wb,sec in sorted(hits,key=lambda x:x[1].line,reverse=True):
                key=(wb,sec.name,sec.tag)
                if key in seen: continue
                seen.add(key)
                base_matches=[(ln,b) for ln,name,b,tag in bases
                              if ln<=n and name.lower()==sec.name.lower()
                              and tag==sec.tag and b<=wb+pc]
                module_base=max(base_matches,key=lambda a:a[0])[1] if base_matches else None
                rva = f"0x{wb+pc-module_base:x}" if module_base else "unknown (no matching module base)"
                print(f"    wow={wb:#x}, module={sec.name}, tag={sec.tag}, section_log_line={sec.line}, rva={rva}")
                if len(seen)>=12:break
            if len(seen)>1:
                print("  Multiple matches: use process identity / exception-record owner to disambiguate.")
        else:
            print("  No confirmed module section encompasses this PC in any logged WoW window.")
            print("  Do not guess the module from a numerically nearby DLL base.")
        print("  Immediate log context:")
        for idx in range(max(0,n-9),min(len(lines),n+9)):
            raw=lines[idx].strip()
            if raw:
                print(f"    {idx+1}: {raw[:240]}")
    print()

def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path, help="Collection directory or single madeira-log.txt")
    ns=ap.parse_args()
    paths = [ns.folder] if ns.folder.is_file() else [
        ns.folder/"madeira-log.txt", ns.folder/"madeira-log.prev.txt"]
    for path in paths:
        parse(path)

if __name__=="__main__":
    main()
