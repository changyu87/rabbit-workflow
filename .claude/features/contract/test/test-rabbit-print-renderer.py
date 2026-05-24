#!/usr/bin/env python3
"""test-rabbit-print-renderer.py — e2e tests for rabbit_print.py.

Asserts the direct-call API: rabbit_print(text, icon, color, format),
rabbit_subline(text, color, icon), and rabbit_block(*lines). No registry,
no message-id lookup, no named wrappers.
"""

import contextlib
import importlib.util
import io
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
MODULE_PATH = os.path.join(FEATURE_DIR, "scripts", "rabbit_print.py")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


# t1: module file exists
if not os.path.isfile(MODULE_PATH):
    fail(f"t1: rabbit_print.py missing at {MODULE_PATH}")
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)
ok("t1: rabbit_print.py exists on disk")

# t2: importable as a module
spec = importlib.util.spec_from_file_location("rabbit_print", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    ok("t2: rabbit_print module imports cleanly")
except Exception as e:
    fail(f"t2: import failed: {e}")
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)

# t3: __all__ is exactly the three direct-call API names
EXPECTED_ALL = {"rabbit_print", "rabbit_subline", "rabbit_block"}
actual_all = set(getattr(mod, "__all__", []))
if actual_all == EXPECTED_ALL:
    ok(f"t3: __all__ is exactly {sorted(EXPECTED_ALL)}")
else:
    fail(f"t3: __all__ mismatch: expected {EXPECTED_ALL}, got {actual_all}")

# t4: named wrappers MUST NOT exist (Plan F.3 retirement)
RETIRED_WRAPPERS = (
    "welcome", "policy_drift", "surface_drift",
    "scope_guard_off", "scope_guard_bypassed", "human_approval_bypass",
    "bypass_permissions_active", "dispatch_bypass_note",
    "skills_updated", "policy_refreshed", "tdd_transition", "tdd_forced",
)
for name in RETIRED_WRAPPERS:
    if getattr(mod, name, None) is None:
        ok(f"t4: retired wrapper '{name}' absent")
    else:
        fail(f"t4: retired wrapper '{name}' still present")

# t5: the three public callables exist
for name in ("rabbit_print", "rabbit_subline", "rabbit_block"):
    if callable(getattr(mod, name, None)):
        ok(f"t5: {name} is callable")
    else:
        fail(f"t5: {name} is not callable")
        print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
        sys.exit(1)

BRAND = "[\U0001f407 rabbit \U0001f407]"
BAR = "━━━"
GREEN_A, GREEN_R = "\x1b[32m", "\x1b[0m"
RED_A, RED_R = "\x1b[31m", "\x1b[0m"
YELLOW_A, YELLOW_R = "\x1b[33m", "\x1b[0m"


def _capture(fn, *args, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        v = fn(*args, **kwargs)
    return v, out.getvalue(), err.getvalue()


# t6: compact format (default)
got, so, se = _capture(mod.rabbit_print, "hello", "✅", "green")
exp = f"{GREEN_A}{BRAND} ✅ hello{GREEN_R}"
if got == exp:
    ok("t6: compact (default) rabbit_print produces brand icon text")
else:
    fail(f"t6: compact mismatch\n  exp: {exp!r}\n  got: {got!r}")
if so == "" and se == "":
    ok("t6b: rabbit_print produces no stdout/stderr side effects")
else:
    fail(f"t6b: rabbit_print produced side effects: stdout={so!r}, stderr={se!r}")

# t7: explicit format="compact"
got, _, _ = _capture(mod.rabbit_print, "x", "i", "red", format="compact")
exp = f"{RED_A}{BRAND} i x{RED_R}"
if got == exp:
    ok("t7: explicit format='compact' renders compact form")
else:
    fail(f"t7: format='compact' mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t8: format="banner" adds the ━━━ decoration
got, _, _ = _capture(mod.rabbit_print, "boot", "✅", "green", format="banner")
exp = f"{GREEN_A}{BRAND} ✅ {BAR} boot {BAR} ✅{GREEN_R}"
if got == exp:
    ok("t8: format='banner' renders brand icon bar text bar icon")
else:
    fail(f"t8: format='banner' mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t9: yellow color exists (was added for dispatch-bypass-note in BACKLOG-29;
# wire-format schema still enumerates green/red/yellow).
got, _, _ = _capture(mod.rabbit_print, "note", "📢", "yellow")
exp = f"{YELLOW_A}{BRAND} 📢 note{YELLOW_R}"
if got == exp:
    ok("t9: color='yellow' renders with [33m ANSI")
else:
    fail(f"t9: yellow mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t10: unknown color raises KeyError
try:
    mod.rabbit_print("x", "i", "purple")
    fail("t10: unknown color did not raise KeyError")
except KeyError:
    ok("t10: unknown color raises KeyError")
except Exception as e:
    fail(f"t10: unknown color raised {type(e).__name__} not KeyError")

# t11: rabbit_subline default (green, no icon)
got, _, _ = _capture(mod.rabbit_subline, "test text")
exp = f"{GREEN_A}{BRAND} test text{GREEN_R}"
if got == exp:
    ok("t11: rabbit_subline default returns green brand text")
else:
    fail(f"t11: rabbit_subline default mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t12: rabbit_subline with color='red'
got, _, _ = _capture(mod.rabbit_subline, "alert", color="red")
exp = f"{RED_A}{BRAND} alert{RED_R}"
if got == exp:
    ok("t12: rabbit_subline color='red'")
else:
    fail(f"t12: rabbit_subline red mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t13: rabbit_subline with icon — icon appears between brand and text
got, _, _ = _capture(mod.rabbit_subline, "revoke now", color="red", icon="🔑")
exp = f"{RED_A}{BRAND} 🔑 revoke now{RED_R}"
if got == exp:
    ok("t13: rabbit_subline with icon='🔑' inserts icon between brand and text")
else:
    fail(f"t13: rabbit_subline icon mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t14: rabbit_subline icon=None matches default behavior
got, _, _ = _capture(mod.rabbit_subline, "plain text", color="green", icon=None)
exp = f"{GREEN_A}{BRAND} plain text{GREEN_R}"
if got == exp:
    ok("t14: rabbit_subline icon=None is identical to no-icon default")
else:
    fail(f"t14: rabbit_subline icon=None mismatch\n  exp: {exp!r}\n  got: {got!r}")

# t15: rabbit_block prepends a single newline and joins with \n
got = mod.rabbit_block("a", "b", "c")
exp = "\na\nb\nc"
if got == exp:
    ok("t15: rabbit_block joins lines with leading newline")
else:
    fail(f"t15: rabbit_block mismatch\n  exp: {exp!r}\n  got: {got!r}")

if FAIL != 0:
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-rabbit-print-renderer: all checks passed.")
