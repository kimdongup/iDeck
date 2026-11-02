#!/usr/bin/env python3
"""Read-only Build114 CEF exception timeline and nearby module maps."""
import argparse
from pathlib import Path
import re

def inspect(path, radius):
    lines = path.read_text(errors="replace").splitlines()
    key = re.compile(r"\[task-exc\].*BREAKPOINT|\[int3-guest\] guest_rip=|dependency_attach failed status=80000003", re.I)
    points = [i for i, line in enumerate(lines) if key.search(line)]
    print(f"{path}: {len(lines)} lines; exception markers={len(points)}")
    for i in points[:9]:
        lo, hi = max(0, i-radius), min(len(lines), i+radius+1)
        print(f"\n=== marker line {i+1}; context {lo+1}-{hi} ===")
        for j in range(lo,hi):
            print(f"{j+1}: {lines[j]}")
    if points:
        first=points[0]
        print("\n=== recent executable/module and CEF events before breakpoint ===")
        pat=re.compile(r"Load module|\[main-exe\]|\[steam-ui-process\]|\[build110-import-fail\]|\[iOS-xins\]")
        matches=[(i+1,line) for i,line in enumerate(lines[:first+1]) if pat.search(line)]
        for n, line in matches[-65:]: print(f"{n}: {line}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("log",type=Path)
    ap.add_argument("--radius",type=int,default=28)
    a=ap.parse_args()
    if not a.log.is_file(): ap.error(f"not found: {a.log}")
    inspect(a.log,max(0,min(a.radius,100)))

if __name__=="__main__": main()
