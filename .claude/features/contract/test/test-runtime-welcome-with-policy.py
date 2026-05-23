#!/usr/bin/env python3
"""test-runtime-welcome-with-policy.py — exercises welcome_with_policy:
returns [print_result (welcome banner), inject_result (policy text)] on
success; single error_result if policy_source is unreadable.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import welcome_with_policy  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: file source -> [print, inject]
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY-BODY\n")
    r = welcome_with_policy("policy.md", repo_root=td)
    if not isinstance(r, list) or len(r) != 2:
        fail(f"t1: expected 2-element list, got {r!r}")
    elif r[0]["type"] != "print" or r[1]["type"] != "inject":
        fail(f"t1: expected [print, inject], got types {[x.get('type') for x in r]}")
    elif r[1]["content"] != "POLICY-BODY\n":
        fail(f"t1: inject content mismatch: {r[1]!r}")
    else:
        ok("t1: file source returns [print_banner, inject_policy]")

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

# t3: welcome banner has fixed text/icon/color
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "p.md"), "w") as f:
        f.write("x")
    r = welcome_with_policy("p.md", repo_root=td)
    p = r[0]
    if (p["text"] == "Rabbit workflow ready"
            and p["icon"] == "rabbit"
            and p["color"] == "green"):
        ok("t3: welcome banner has fixed text/icon/color")
    else:
        fail(f"t3: unexpected banner: {p!r}")

# t4: missing source -> single error_result (not a list)
with tempfile.TemporaryDirectory() as td:
    r = welcome_with_policy("missing.md", repo_root=td)
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t4: missing source returns single error_result")
    else:
        fail(f"t4: expected error dict, got {r!r}")

if FAIL:
    print("test-runtime-welcome-with-policy: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-welcome-with-policy: all checks passed.")
