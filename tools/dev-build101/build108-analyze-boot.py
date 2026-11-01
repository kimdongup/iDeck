#!/usr/bin/env python3
"""Offline diagnosis of existing Build107/108 Madeira logs. Never accesses the phone."""
import argparse
import pathlib
import re

EXIT = re.compile(r"\[Wine child thread\] child exited with code (-?\d+)")
END = re.compile(r"\[steam-ui-process\] event=end kind=(\w+) slot=(\d+) machine=([0-9a-fA-F]+)")
IMPORTANT = re.compile(r"ec-child-ntdll|load_child_ec_ntdll|BOOT FAILED|failed to load|wine-bootstrap|\[FEX-iOS\]|\[wow64-init\]|\[file-wfail\]|\[file-fail\]|\[main-exe\]|\[Wine child\]|\[steam-ui-process\]|\[term-stack\]|\[x64-data-imp\]|\[valloc\].*LIMIT-VIOLATED", re.I)
FILEFAIL = re.compile(r"\[file-(?:wfail|fail)\]")
REDACT = re.compile(r"/(?:private/var|var/mobile)/[^\s]+|[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}",re.I)

def analyze(path, out):
    lines=path.read_text(encoding="utf-8", errors="replace").splitlines()
    found=[]
    for i,line in enumerate(lines):
        m=EXIT.search(line)
        if not m: continue
        nxt=next((END.search(lines[j]) for j in range(i+1,min(i+8,len(lines))) if END.search(lines[j])),None)
        machine=nxt.group(3) if nxt else "unknown"
        kind=nxt.group(1) if nxt else "unknown"
        start=max(0,i-95)
        candidates=[(j,lines[j]) for j in range(start,i) if IMPORTANT.search(lines[j])]
        detail=[(j,v) for j,v in candidates if not FILEFAIL.search(v)]
        found.append((i,m.group(1),machine,kind,detail[-28:],candidates[-18:]))
    output=[f"Source: {path.name} ({len(lines)} lines)",f"Exit events: {len(found)}", ""]
    for idx,(line,code,machine,kind,detail,candidates) in enumerate(found,1):
        codehex=f"0x{(int(code)&0xffffffff):08x}"
        output.append(f"=== exit #{idx}: log line {line+1}, machine={machine}, kind={kind}, exit={code} ({codehex}) ===")
        for j,v in detail:
            output.append(f"{j+1}: {REDACT.sub('[path/id]',v)[:320]}")
        output.append("Nearby file probes (not necessarily fatal):")
        for j,v in candidates:
            if FILEFAIL.search(v):output.append(f"{j+1}: {REDACT.sub('[path/id]',v)[:260]}")
        output.append("")
    if not found:output.append("No child exit events found.")
    out.write_text("\n".join(output)+"\n",encoding="utf-8")
    print("\n".join(output[:3]))
    for i,code,machine,kind,_,_ in found:print(f"line {i+1}: machine={machine} kind={kind} exit=0x{int(code)&0xffffffff:08x}")
    print("Report:",out)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("log",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path)
    a=p.parse_args()
    if not a.log.is_file():p.error("log not found")
    analyze(a.log,a.output or a.log.with_name("build108-boot-analysis.txt"))
if __name__=="__main__":main()
