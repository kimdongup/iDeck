#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see ../../LICENSE-EXCEPTION.md (this file only).
"""Emit or apply the bounded pool patch; never reduce the CEF build graph."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parent
CONTROL = json.loads((BASE / "public-control.json").read_text())
HEADER = "base/allocator/partition_allocator/src/partition_alloc/partition_address_space.h"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_header(data, pool_mib):
    if sha(data) != CONTROL["header_sha256"]:
        raise ValueError("Unrecognized original allocator header; preserve existing changes")
    if pool_mib not in (256, 512, 1024):
        raise ValueError("Pool size must be one of the reviewed candidates")
    text = data.decode("utf-8")
    for name in ("kRegularPoolSize", "kBRPPoolSize"):
        declaration = f"static constexpr size_t {name} = kPoolMaxSize;"
        if text.count(declaration) != 1:
            raise ValueError("Non-unique pool declaration")
        text = text.replace(declaration, f"static constexpr size_t {name} = {pool_mib} * 1024 * 1024;")
    return text.encode("utf-8")


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def checked_checkout(root):
    if git(root, "rev-parse", "HEAD") != CONTROL["chromium_revision"]:
        raise ValueError("Wrong Chromium revision")
    if git(root / "cef", "rev-parse", "HEAD") != CONTROL["cef_revision"]:
        raise ValueError("Wrong public-control CEF revision")
    if sha((root / "cef/BUILD.gn").read_bytes()) != CONTROL["cef_build_gn_sha256"]:
        raise ValueError("CEF build graph changed; focused chrome_elf trees are unsuitable")
    if sha((root / "cef/include/cef_api_hash.h").read_bytes()) != CONTROL["cef_api_header_sha256"]:
        raise ValueError("CEF API declarations changed")
    if git(root, "status", "--porcelain", "--", HEADER):
        raise ValueError("Preserve modified allocator header")
    if (root / "ideck-elf-source.json").exists():
        raise ValueError("Use a fresh full CEF checkout, not the focused component tree")
    return root / HEADER


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--header", type=Path, help="Emit patch only; do not modify this file")
    source.add_argument("--checkout", type=Path, help="Apply to a prepared full CEF source checkout")
    parser.add_argument("--output", type=Path, required=True, help="New directory for receipts")
    parser.add_argument("--pool-mib", type=int, choices=(256, 512, 1024), default=1024)
    args = parser.parse_args()
    header = checked_checkout(args.checkout.resolve()) if args.checkout else args.header.resolve()
    original = header.read_bytes()
    candidate = patch_header(original, args.pool_mib)
    # Every precondition is checked before touching the checkout.
    args.output.mkdir(parents=True, exist_ok=False)
    patch = "".join(difflib.unified_diff(original.decode().splitlines(True),
                                      candidate.decode().splitlines(True),
                                      fromfile="a/" + HEADER, tofile="b/" + HEADER))
    (args.output / "small-pools.patch").write_text(patch)
    (args.output / "partition_address_space.h").write_bytes(candidate)
    if args.checkout:
        header.write_bytes(candidate)
    receipt = dict(control=CONTROL, pool_mib=args.pool_mib, original_sha256=sha(original),
                   patched_sha256=sha(candidate), patch_sha256=sha(patch.encode()),
                   applied_to_checkout=bool(args.checkout), compiled=False,
                   replacement_eligible=False, baseline_abi_match=False,
                   reason="Public control API hashes differ from the observed Steam libcef")
    (args.output / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("pool_mib", "patched_sha256", "compiled", "replacement_eligible")}))


if __name__ == "__main__":
    main()
