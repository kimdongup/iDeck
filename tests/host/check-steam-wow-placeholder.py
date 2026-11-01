#!/usr/bin/env python3
"""Static host regression test for early WoW64 placeholders on Steam UI launches.

The actual guest-window C mapping/adoption is exercised by check-lazy-windows.py.
This test verifies the Swift launch path arms it BEFORE Wine initializes and
non-Steam launch paths are not made to reserve 4 GB by default.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
src = (root / "app/Madeira/ContentView.swift").read_text()
virt = (root / "build/ntdll-unix/virtual_ios.c").read_text()
loader = (root / "build/ntdll-unix/loader_ios.c").read_text()

head = src.index("private func runWineFullSequence(profile: LibraryEntry? = nil, steamUI: Bool = false)")
end = src.index("private func ", head + 15)
fn = src[head:end]

assert "if steamUI {" in fn
assert fn.index("MadeiraConfig.applyGame(nil)") < fn.index("if steamUI {")
assert fn.index('setenv("MADEIRA_WOW_PLACEHOLDERS", value, 1)') < fn.index("// Step 1: Allocate JIT pool")
assert fn.index('setenv("MADEIRA_WOW_PLACEHOLDERS", value, 1)') < fn.index("self.startWineProcess()")
assert 'MadeiraConfig.get("env.MADEIRA_WOW_PLACEHOLDERS")?' in fn
assert 'configured == "0" ? "0" : "1"' in fn
assert 'logStore.log("[wow-window] Steam early placeholders=\\(value)' in fn
assert 'unsetenv("MADEIRA_WOW_PLACEHOLDERS")' in fn
assert 'unsetenv("MADEIRA_WOW_VA_CENSUS")' in fn
assert 'unsetenv("MADEIRA_WOW_EARLY_HOLD")' in fn
assert 'MadeiraConfig.get("env.MADEIRA_WOW_EARLY_HOLD")?' in fn
assert 'setenv("MADEIRA_WOW_EARLY_HOLD", early == "1" ? "1" : "0", 1)' in fn
assert 'jit_wow_early_hold_try()' in fn
assert fn.index('jit_wow_early_hold_try()') < fn.index("// Step 1: Allocate JIT pool")

assert 'setenv("MADEIRA_WOW_VA_CENSUS", census == "1" ? "1" : "0", 1)' in fn
for stage in ("app-pre-jit", "app-post-jit", "app-pre-wineserver", "app-pre-wine"):
    assert f'jit_wow_va_probe("{stage}")' in fn
assert fn.index('jit_wow_va_probe("app-pre-jit")') < fn.index("// Step 1: Allocate JIT pool")
assert fn.index('jit_wow_va_probe("app-pre-wine")') < fn.index("self.startWineProcess()")
assert 'runWineFullSequence(steamUI: true)' in src

session = virt[virt.index("static void ios_wow_session_start(void)"):][:1000]
assert 'ios_wow_env_ulong( "MADEIRA_WOW_PLACEHOLDERS", 0 ) == 1' in session
assert session.index('ios_wow_reserve_placeholders( want )') > session.index("ios_wow_map_allows_window()")
virtual_init = virt[virt.index("void virtual_init(void)"):][:70000]
assert "ios_wow_session_start();" in virtual_init
assert loader.index("ios_reserve_fex_arena();") < loader.index("load_ntdll();")
print("PASS: Steam-only default early placeholders, env override, pre-Wine timing")
print("PASS: C guest-window reservation hook and FEX-before-PE invariant")
