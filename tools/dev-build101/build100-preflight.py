#!/usr/bin/env python3
"""Read-only iDeck experimental Build100 dependency/source audit.

Does not write to the source repo, install software, or access credentials.
Usage: python3 build100-preflight.py [--repo DIR] [--output FILE] [--require-ready]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "iDeck"
REQUIRED_LIBS = [
    "libavcodec.a", "libavformat.a", "libavutil.a",
    "libdxmt_combined.a", "libgmp.a", "libgnutls.a",
    "libhogweed.a", "libmadeira_rppairing.a", "libnettle.a",
    "libntdll_unix.a", "libswresample.a", "libwin32u_unix.a",
    "libwineserver.a"
]
SUBMODULES = ["FEX", "wine", "dxmt", "madeira-dock"]
# Xcode directly links these seven archives from FEX/build-ios. 13/13
# Madeira-local archives do NOT imply a buildable app without these.
FEX_ARCHIVES = [
    "FEXCore/Source/libFEXCore.a",
    "FEXCore/Source/libFEXCore_Base.a",
    "FEXCore/Source/libJemallocLibs.a",
    "External/fmt/libfmt.a",
    "External/cephes/libcephes_128bit.a",
    "External/xxhash/cmake_unofficial/libxxhash.a",
    "External/SoftFloat-3e/libsoftfloat_3e.a",
]
RUNTIME = [
    "app/Madeira/aarch64-windows/xtajit.dll",
    "app/Madeira/arm64ec-windows/xtajit64.dll",
]
# These are folder references in the project's PBXResourcesBuildPhase.
# A missing folder is an Xcode Copy Bundle Resources error, regardless of
# whether all C/ObjC static libraries are available.
BUNDLE_RESOURCE_FOLDERS = [
    "app/Madeira/aarch64-windows",
    "app/Madeira/arm64ec-windows",
    "app/Madeira/i386-windows",
    "app/Madeira/x86_64-vcruntime",
]
# Distinct from Xcode buildability: these are the Wine PE runtime modules
# named in SteamUIExperiment.swift for 32-bit guest bootstrapping.
STEAM_WOW64_FILES = [
    "app/Madeira/aarch64-windows/xtajit.dll",
    "app/Madeira/aarch64-windows/cmd.exe",
    "app/Madeira/aarch64-windows/explorer.exe",
    "app/Madeira/i386-windows/ntdll.dll",
]
# Source of truth: iDeck/tools/fetch-vcruntime.md (14 expected binaries).
# Folder existence or two baseline DLLs does NOT prove the x64 runtime is ready.
# Microsoft files must be supplied locally under the applicable licence.
VC_X64_REQUIRED_DLLS = [
    "concrt140.dll", "msvcp140.dll", "msvcp140_1.dll",
    "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll", "vcamp140.dll", "vccorlib140.dll",
    "vcomp140.dll", "vcruntime140.dll", "vcruntime140_1.dll",
    "vcruntime140_threads.dll", "mfc140.dll", "mfc140u.dll",
]
# The JIT helper strongly links the 1.9.0 binary, not merely its Swift headers.
# SHA-256 is from the exact verified upstream release archive referenced in docs/JIT.md.
STIKJIT_BINARY_PATH = "app/Frameworks/StikJIT.xcframework/ios-arm64/StikJIT.framework/StikJIT"
STIKJIT_BINARY_SHA256 = "f15ad5c6766fa07d545be283c1c99eccde6a8baa97d73978a09ec080ca6381df"


def cmd(argv: list[str], cwd: Path | None = None, timeout: int = 15) -> tuple[int, str]:
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout.strip() or p.stderr.strip())[:6000]
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        return 127, str(exc)


def readable_file(p: Path) -> bool:
    return p.is_file() and p.stat().st_size > 0


def prefix_template_verified(p: Path) -> bool:
    """Require actual Wine registry/skeleton; a dummy tarball is not enough."""
    if not readable_file(p):
        return False
    try:
        with tarfile.open(p, "r:gz") as archive:
            members = archive.getmembers()
            names = {m.name.rstrip("/") for m in members}
            required = {
                "prefix/system.reg", "prefix/user.reg",
                "prefix/userdef.reg", "prefix/.update-timestamp",
                "prefix/drive_c/windows/system32",
            }
            if not required.issubset(names):
                return False
            for reg in ("system.reg", "user.reg", "userdef.reg"):
                entry = archive.getmember(f"prefix/{reg}")
                if not entry.isfile() or entry.size < 30:
                    return False
                stream = archive.extractfile(entry)
                if stream is None or not stream.read(64).startswith(b"WINE REGISTRY Version"):
                    return False
            for member in members:
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    return False
                if member.issym() or member.islnk():
                    # iOS extraction intentionally does not restore symlinks.
                    return False
                if not member.isfile() and not member.isdir():
                    return False
            return True
    except (OSError, tarfile.TarError):
        return False


def stikjit_binary_verified(p: Path) -> bool:
    """Exact pinned upstream iOS arm64 Mach-O, not an empty framework shell."""
    try:
        if not readable_file(p):
            return False
        with p.open("rb") as handle:
            h = handle.read(12)
        if len(h) < 12:
            return False
        magic, cpu = struct.unpack_from("<II", h)
        if magic != 0xFEEDFACF or cpu != 0x0100000C:
            return False
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        return digest == STIKJIT_BINARY_SHA256
    except (OSError, struct.error):
        return False


def pe_x64_signed(p: Path) -> bool:
    """Require an intact, signed PE32+ AMD64 image; do not alter vendor files."""
    try:
        if not readable_file(p):
            return False
        with p.open("rb") as f:
            h = f.read(4096)
        if len(h) < 256 or h[:2] != b"MZ":
            return False
        pe, = struct.unpack_from("<I", h, 0x3c)
        if pe + 24 + 112 + 5 * 8 > len(h):
            return False
        if h[pe:pe + 4] != bytes((0x50, 0x45, 0, 0)):
            return False
        machine, = struct.unpack_from("<H", h, pe + 4)
        magic, = struct.unpack_from("<H", h, pe + 24)
        if machine != 0x8664 or magic != 0x20b:
            return False
        off, size = struct.unpack_from("<II", h, pe + 24 + 112 + 4 * 8)
        return bool(off and size and off + size <= p.stat().st_size)
    except (OSError, ValueError, struct.error):
        return False


def candidate_sources(root: Path) -> list[dict]:
    home = Path.home()
    guesses = [
        home / "Bazel/iDeck", home / "Bazel/Madeira",
        home / "Developer/iDeck", home / "Developer/Madeira",
        home / "Projects/iDeck", home / "Projects/Madeira",
        home / "Downloads/iDeck", home / "Downloads/Madeira",
        home / "iDeck", home / "Madeira",
        Path("/Volumes/Repository/iDeck"),
        Path("/Volumes/Repository/Madeira"),
        Path("/Volumes/Repository/cokacremote/iDeck"),
    ]
    seen = {str(root.resolve())}
    # Spotlight avoids recursively traversing large external SSD trees.
    if platform.system() == "Darwin" and shutil.which("mdfind"):
        status, result = cmd(["mdfind", "kMDItemFSName == 'Madeira.xcodeproj'"], timeout=15)
        if status == 0:
            for line in result.splitlines()[:35]:
                x = Path(line).expanduser()
                if x.name == "Madeira.xcodeproj":
                    guesses.append(x.parent.parent)
    results = []
    for p in guesses:
        try:
            canonical = str(p.resolve())
        except OSError:
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        project = p / "app/Madeira.xcodeproj/project.pbxproj"
        if not readable_file(project):
            continue
        libs = sum(readable_file(p / "app/Madeira" / name) for name in REQUIRED_LIBS)
        modules = sum((p / mod / ".git").exists() for mod in SUBMODULES)
        rc, sha = cmd(["git", "rev-parse", "--short", "HEAD"], cwd=p, timeout=3)
        results.append({"path": str(p), "native_libs": libs,
                        "submodules_present": modules,
                        "revision": sha if rc == 0 else "unknown"})
    return sorted(results, key=lambda x:(-x["native_libs"],-x["submodules_present"]))


def collect(root: Path, discover: bool) -> dict:
    project = root / "app/Madeira.xcodeproj/project.pbxproj"
    pbx = project.read_text(errors="replace") if project.is_file() else ""
    missing_libs = [x for x in REQUIRED_LIBS if not readable_file(root/"app/Madeira"/x)]
    modules: dict[str, dict] = {}
    for name in SUBMODULES:
        folder = root / name
        # A missing submodule can be an EMPTY directory. git -C there would
        # silently resolve the PARENT repository: require a local .git marker.
        linked = folder.is_dir() and (folder / ".git").exists()
        rc, sha = cmd(["git", "rev-parse", "HEAD"], cwd=folder, timeout=4) if linked else (127,"")
        trc, tree_line = cmd(["git", "ls-tree", "HEAD", name], cwd=root, timeout=4)
        expected_match = re.search(r"^160000 commit ([0-9a-f]{40})\s", tree_line) if trc == 0 else None
        pinned = expected_match.group(1) if expected_match else None
        modules[name] = {
            "checked_out": bool(linked and rc == 0 and len(sha) == 40),
            "sha": sha if rc == 0 else None,
            "gitlink_pin": pinned,
            "matches_pinned_revision": bool(linked and rc == 0 and sha == pinned),
        }
    rc, version = cmd(["xcodebuild", "-version"], timeout=15) if platform.system()=="Darwin" else (127,"Not running on macOS")
    _, branch = cmd(["git", "branch", "--show-current"], cwd=root, timeout=3)
    _, git_sha = cmd(["git", "rev-parse", "HEAD"], cwd=root, timeout=3)
    _, remaining = cmd(["df", "-k", str(root)], timeout=5)
    patched = (
        "jit_wow_early_hold_try()" in (root/"app/Madeira/ContentView.swift").read_text(errors="replace")
        if (root/"app/Madeira/ContentView.swift").is_file() else False
    ) and (
        "ios_wow_import_app_early_hold" in (root/"build/ntdll-unix/virtual_ios.c").read_text(errors="replace")
        if (root/"build/ntdll-unix/virtual_ios.c").is_file() else False
    )
    runtime_missing = [x for x in RUNTIME if not readable_file(root/x)]
    fex_missing = [x for x in FEX_ARCHIVES if not readable_file(root/"FEX/build-ios"/x)]
    resource_folders_missing = [x for x in BUNDLE_RESOURCE_FOLDERS if not (root/x).is_dir()]
    steam_wow64_missing = [x for x in STEAM_WOW64_FILES if not readable_file(root/x)]
    stikjit_valid = stikjit_binary_verified(root / STIKJIT_BINARY_PATH)
    prefix_valid = prefix_template_verified(root / "app/Madeira/prefix-template.tar.gz")
    vc_folder = root / "app/Madeira/x86_64-vcruntime"
    vc_files = ({p.name.casefold(): p for p in vc_folder.iterdir() if readable_file(p)}
                if vc_folder.is_dir() else {})
    vc_missing = [x for x in VC_X64_REQUIRED_DLLS if x.casefold() not in vc_files]
    vc_invalid = [x for x in VC_X64_REQUIRED_DLLS
                  if x.casefold() in vc_files and not pe_x64_signed(vc_files[x.casefold()])]
    out = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "repo": str(root), "git_head": git_sha, "git_branch": branch,
        "xcode": version, "xcode_available": rc==0,
        "project_exists": bool(pbx), "steam_wow64_patch_present": bool(patched),
        "missing_native_libs": missing_libs,
        "found_native_libs": len(REQUIRED_LIBS)-len(missing_libs),
        "native_libs_required": len(REQUIRED_LIBS),
        "fex_static_libs_found": len(FEX_ARCHIVES)-len(fex_missing),
        "fex_static_libs_required": len(FEX_ARCHIVES),
        "missing_fex_static_libs": fex_missing,
        "submodules": modules,
        "missing_runtime_components": runtime_missing,
        "missing_xcode_resource_folders": resource_folders_missing,
        "stikjit_1_9_0_ios_arm64_binary_verified": stikjit_valid,
        "stikjit_binary_path": STIKJIT_BINARY_PATH,
        "wine_prefix_template_verified": prefix_valid,
        "microsoft_vc_x64_runtime_required": len(VC_X64_REQUIRED_DLLS),
        "microsoft_vc_x64_runtime_found": len(VC_X64_REQUIRED_DLLS) - len(vc_missing) - len(vc_invalid),
        "missing_microsoft_vc_x64_runtime_dlls": vc_missing,
        "invalid_microsoft_vc_x64_runtime_dlls": vc_invalid,
        "missing_steam_wow64_boot_files": steam_wow64_missing,
        "steam_wow64_bootstrap_files_present": not steam_wow64_missing,
        "available_space_df": remaining,
        "other_candidate_sources": candidate_sources(root) if discover else [],
    }
    out["ready_for_build_attempt"] = (
        out["xcode_available"] and out["project_exists"] and out["steam_wow64_patch_present"]
        and not missing_libs and not fex_missing
        and all(v["matches_pinned_revision"] for v in modules.values())
        and not runtime_missing and not resource_folders_missing
        and not vc_missing and not vc_invalid and stikjit_valid and prefix_valid
    )
    return out


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=HERE/"diagnostics/mac-build100-preflight.json")
    parser.add_argument("--no-discover", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--verify-prefix", type=Path, default=None,
                        help="Validate only the Wine prefix template archive")
    args=parser.parse_args()
    if args.verify_prefix is not None:
        ok = prefix_template_verified(args.verify_prefix.expanduser())
        print("Wine prefix template:", "VERIFIED" if ok else "MISSING OR INVALID")
        return 0 if ok else 4
    root=args.repo.expanduser().resolve()
    results=collect(root, not args.no_discover)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,indent=2,ensure_ascii=False)+"\n")
    print("=== iDeck Build100 preflight ===")
    print("Host:",results["host_platform"])
    print("Source:",root)
    print("Xcode:",results["xcode"].replace("\n"," / "))
    print("Steam WoW64 patch:", "PRESENT" if results["steam_wow64_patch_present"] else "MISSING")
    print(f'Native libraries: {results["found_native_libs"]}/{results["native_libs_required"]}')
    if results["missing_native_libs"]:
        print("  Missing:",", ".join(results["missing_native_libs"]))
    print(f'FEX static libraries: {results["fex_static_libs_found"]}/{results["fex_static_libs_required"]}')
    if results["missing_fex_static_libs"]:
        print("  Missing FEX:",", ".join(results["missing_fex_static_libs"]))
    for name,value in results["submodules"].items():
        print(f'  {name}: {value["sha"] if value["checked_out"] else "NOT CHECKED OUT"}')
    if results["missing_runtime_components"]:
        print("Runtime missing:",", ".join(results["missing_runtime_components"]))
    if results["missing_xcode_resource_folders"]:
        print("Xcode resource folders missing:",", ".join(results["missing_xcode_resource_folders"]))
    print("StikJIT 1.9.0 iOS ARM64 binary:", "VERIFIED" if results["stikjit_1_9_0_ios_arm64_binary_verified"] else "MISSING OR INVALID")
    if not results["stikjit_1_9_0_ios_arm64_binary_verified"]:
        print("  Required StikJIT binary:", results["stikjit_binary_path"])
    print("Wine prefix template:", "VERIFIED" if results["wine_prefix_template_verified"] else "MISSING OR INVALID")
    print(f'Microsoft VC++ x64 runtime: {results["microsoft_vc_x64_runtime_found"]}/{results["microsoft_vc_x64_runtime_required"]} verified')
    if results["missing_microsoft_vc_x64_runtime_dlls"]:
        print("Microsoft VC++ x64 runtime DLLs missing:",", ".join(results["missing_microsoft_vc_x64_runtime_dlls"]))
    if results["invalid_microsoft_vc_x64_runtime_dlls"]:
        print("Microsoft VC++ x64 runtime DLLs invalid/unsigned:",", ".join(results["invalid_microsoft_vc_x64_runtime_dlls"]))
    if results["missing_steam_wow64_boot_files"]:
        print("Steam WoW64 boot files missing:",", ".join(results["missing_steam_wow64_boot_files"]))
    for c in results["other_candidate_sources"]:
        print("Found older source:",c["path"],
              f'libs={c["native_libs"]}/{len(REQUIRED_LIBS)}',
              f'submodules={c["submodules_present"]}/4',
              f'rev={c["revision"]}')
    print("Can attempt Xcode build:", results["ready_for_build_attempt"])
    print("Report saved:",args.output)
    if args.require_ready and not results["ready_for_build_attempt"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
