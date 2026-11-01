#!/usr/bin/env python3
"""Build107 iPhone Wine bootstrap log collection. Read-only; never prints raw logs."""
import argparse
import datetime
import pathlib
import re
import subprocess
import sys

BUNDLE="com.kimdongup.ideck.build100"
NAMES=("madeira-log.txt","madeira-log.prev.txt","ideck-command-result.txt","ideck-focus-status.txt","ideck-input-status.txt")
FILTER=re.compile(r"ec-child-ntdll|load_child_ec_ntdll|BOOT FAILED|child-boot-fail|Wine child|steam-ui-process|wine-bootstrap|PE loaded|Steam|status=0x|0xc0000135",re.I)
REDACT=re.compile(r"(?:/private/var/[^\s\]\)]+|/var/mobile/[^\s\]\)]+|[A-Z]:\\[^\s\]\)]+|(?:[0-9A-F]{8}-){3}[0-9A-F]{8})",re.I)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--device",required=True,help="iPhone UDID, not printed")
    parser.add_argument("--output",default=None,help="Local diagnostics directory")
    args=parser.parse_args()
    if sys.platform != "darwin": raise SystemExit("Run on the Mac with Xcode.")
    base=pathlib.Path(args.output).expanduser() if args.output else pathlib.Path.home()/"Downloads"/("ideck-build107-device-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    base.mkdir(parents=True,exist_ok=True)
    print("Build107 device log collection (read-only)")
    found=0
    for name in NAMES:
        dest=base/name
        cmd=["xcrun","devicectl","device","copy","from","--device",args.device,"--domain-type","appDataContainer","--domain-identifier",BUNDLE,"--source",f"Documents/{name}","--destination",str(dest)]
        try:
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=75)
        except subprocess.TimeoutExpired:
            print(name,": timed out");continue
        if result.returncode or not dest.is_file():
            print(name,": unavailable (not necessarily an app error)");continue
        found+=1
        print(name,": collected",dest.stat().st_size,"bytes")
        if not name.startswith("madeira-log"):continue
        matches=[REDACT.sub("[path/id]",line.strip()) for line in dest.read_text(errors="replace").splitlines() if FILTER.search(line)]
        print("  diagnostic matches:",len(matches))
        critical=re.compile(r"ec-child-ntdll|load_child_ec_ntdll|BOOT FAILED|child-boot-fail|failed to load|missing.*dll|STATUS_DLL_NOT_FOUND|c0000135|import.*fail|module.*not found",re.I)
        critical_lines=[REDACT.sub("[path/id]",line.strip()) for line in dest.read_text(errors="replace").splitlines() if critical.search(line)]
        print("  critical lines:",len(critical_lines))
        for line in critical_lines[:90]: print("  CRITICAL",line[:360])
        print("  final chronological events:")
        for line in matches[-20:]: print(" ",line[:320])
    print("Local files:",base)
    if found==0: print("No files could be read; device container log location needs investigation.")

if __name__=="__main__":main()
