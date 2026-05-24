#!/usr/bin/env python3
"""test-runtime-welcome-with-policy.py — exercises welcome_with_policy:
returns [banner_result (welcome banner), inject_result (policy text)] on
success; when sublines is given, also returns subline_result items between
banner and inject; single error_result if policy_source is unreadable.

Also exercises banner_result and subline_result factories.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import welcome_with_policy, banner_result, subline_result  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# --- banner_result factory ---

b = banner_result("Welcome", "✅", "green")
if (b.get("type") == "banner"
        and b.get("text") == "Welcome"
        and b.get("icon") == "✅"
        and b.get("color") == "green"):
    ok("t-banner-1: banner_result carries inline text/icon/color")
else:
    fail(f"t-banner-1: unexpected banner_result: {b!r}")

# --- subline_result factory ---

s = subline_result("hello")
if s.get("type") == "subline" and s.get("text") == "hello" and s.get("color") == "green":
    ok("t-subline-1: subline_result defaults to green")
else:
    fail(f"t-subline-1: unexpected subline_result: {s!r}")

s2 = subline_result("warn", color="red")
if s2.get("type") == "subline" and s2.get("color") == "red":
    ok("t-subline-2: subline_result accepts explicit color")
else:
    fail(f"t-subline-2: unexpected subline_result: {s2!r}")

# --- welcome_with_policy without sublines (existing shape) ---

# t1: file source -> [banner, inject] (banner replaces former print)
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY-BODY\n")
    r = welcome_with_policy("policy.md", repo_root=td)
    if not isinstance(r, list) or len(r) != 2:
        fail(f"t1: expected 2-element list, got {r!r}")
    elif r[0]["type"] != "banner" or r[1]["type"] != "inject":
        fail(f"t1: expected [banner, inject], got types {[x.get('type') for x in r]}")
    elif r[1]["content"] != "POLICY-BODY\n":
        fail(f"t1: inject content mismatch: {r[1]!r}")
    else:
        ok("t1: file source returns [banner, inject_policy]")

# t2: directory source -> concat *.md in alphabetical order
with tempfile.TemporaryDirectory() as td:
    pol = os.path.join(td, "policy")
    os.makedirs(pol)
    with open(os.path.join(pol, "2-coding.md"), "w") as f:
        f.write("CODING\n")
    with open(os.path.join(pol, "1-philosophy.md"), "w") as f:
        f.write("PHILOSOPHY\n")
    r = welcome_with_policy("policy", repo_root=td)
    if r[1]["content"] == "PHILOSOPHY\nCODING\n":
        ok("t2: directory source concatenates *.md alphabetically")
    else:
        fail(f"t2: unexpected inject content: {r[1]!r}")

# t3: welcome banner carries the welcome text/icon/color inline
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "p.md"), "w") as f:
        f.write("x")
    r = welcome_with_policy("p.md", repo_root=td)
    p = r[0]
    if (p["type"] == "banner"
            and "Welcome" in p.get("text", "")
            and p.get("icon") == "✅"
            and p.get("color") == "green"):
        ok("t3: welcome banner carries inline welcome text + ✅ + green")
    else:
        fail(f"t3: unexpected banner result: {p!r}")

# t4: missing source -> single error_result (not a list)
with tempfile.TemporaryDirectory() as td:
    r = welcome_with_policy("missing.md", repo_root=td)
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t4: missing source returns single error_result")
    else:
        fail(f"t4: expected error dict, got {r!r}")

# --- welcome_with_policy with sublines ---

# t5: sublines=[] -> same shape as without sublines ([banner, inject])
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "p.md"), "w") as f:
        f.write("BODY")
    r = welcome_with_policy("p.md", sublines=[], repo_root=td)
    if isinstance(r, list) and len(r) == 2 and r[0]["type"] == "banner" and r[1]["type"] == "inject":
        ok("t5: empty sublines returns [banner, inject]")
    else:
        fail(f"t5: unexpected result with empty sublines: {r!r}")

# t6: sublines provided -> [banner, subline_1, subline_2, inject]
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "p.md"), "w") as f:
        f.write("BODY")
    subs = [
        {"text": "line-A"},
        {"text": "line-B", "color": "red"},
    ]
    r = welcome_with_policy("p.md", sublines=subs, repo_root=td)
    if not isinstance(r, list) or len(r) != 4:
        fail(f"t6: expected 4-element list, got len={len(r) if isinstance(r, list) else 'N/A'}: {r!r}")
    elif r[0]["type"] != "banner":
        fail(f"t6: expected banner first, got {r[0]!r}")
    elif r[1]["type"] != "subline" or r[1]["text"] != "line-A" or r[1]["color"] != "green":
        fail(f"t6: subline[0] mismatch: {r[1]!r}")
    elif r[2]["type"] != "subline" or r[2]["text"] != "line-B" or r[2]["color"] != "red":
        fail(f"t6: subline[1] mismatch: {r[2]!r}")
    elif r[3]["type"] != "inject":
        fail(f"t6: expected inject last, got {r[3]!r}")
    else:
        ok("t6: sublines=[2] returns [banner, subline, subline, inject]")

# t7: subline default color is green when not specified
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "p.md"), "w") as f:
        f.write("X")
    subs = [{"text": "no-color-specified"}]
    r = welcome_with_policy("p.md", sublines=subs, repo_root=td)
    sl = r[1]
    if sl["type"] == "subline" and sl["color"] == "green":
        ok("t7: subline without color defaults to green")
    else:
        fail(f"t7: unexpected subline color: {sl!r}")

# t8: missing source with sublines still returns error_result
with tempfile.TemporaryDirectory() as td:
    r = welcome_with_policy("missing.md", sublines=[{"text": "x"}], repo_root=td)
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t8: missing source with sublines returns error_result")
    else:
        fail(f"t8: expected error dict, got {r!r}")

if FAIL:
    print("test-runtime-welcome-with-policy: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-welcome-with-policy: all checks passed.")
