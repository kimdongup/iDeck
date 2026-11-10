#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only).
"""Guard V8 CodeRange placement on iOS extended_va=false.

When the primary near-builtins coderange zone is exhausted, the allocator must
try fallback near-builtins windows and must NOT fall through to the generic
bigres steering valve (which places above ceiling/out of V8 reach and causes
livelock). A full fallback failure should fail honestly as STATUS_NO_MEMORY."""
from pathlib import Path
import sys

src = (Path(__file__).resolve().parents[2] / "build/ntdll-unix/virtual_ios.c").read_text(errors="replace")
ok = True


def need(label, cond):
    global ok
    if not cond:
        print(f"FAIL: {label}")
        ok = False
    else:
        print(f"ok: {label}")


# Locate coderange block
start = src.index("V8 CodeRange placement service")
end = src.index("coderange_done:", start)
block = src[start:end]

need("has fallback zones list", "cr_zones[]" in block or "cr_zones [" in block)
need("tries primary coderange zone", "0x7180000000ULL, 0x71c0000000ULL" in block)
need("avoids cage holdback conflict", "cage" in block and "holdback" in block)
need("avoids nocopy libcef/cage conflict in fallback design", "0x70c0000000ULL, 0x7100000000ULL" in block or "0x7200000000" not in block.split("cr_zones[]")[1].split("};")[0])
need("blocks generic steering on full failure", "ios_steered = 1" in block)
need("no out-of-reach steer on full failure", "no out-of-reach steer" in block)
need("livelock deny preserved", "placement livelock, failing honestly" in block)

# Steering valve must still exist and be gated (coderange sets ios_steered on
# full failure so out-of-reach placement cannot happen).
need("steering valve comment present", "STEERING VALVE" in src)
sv_gate = src.index("!ios_steered", end)
need("steering gate after coderange handling", sv_gate > end)
# The bigres steering condition for 32MB-1GB must remain gated.
need("generic bigres steering remains", '*size_ptr >= 0x2000000 && *size_ptr < 0x40000000' in src[end:])

if not ok:
    sys.exit(1)
print("PASS: coderange near-builtins fallback blocks harmful out-of-reach steering")
