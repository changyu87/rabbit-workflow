#!/usr/bin/env python3
"""test-runtime-check-counter-threshold-refresh.py — exercises
check_counter_threshold_refresh: increments a counter file each
invocation; on threshold, resets counter to 0 and returns inject_result
with the contents of `source` (file or directory of *.md files
concatenated alphabetically).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_counter_threshold_refresh  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def read_counter(td):
    p = os.path.join(td, ".rabbit-prompt-counter")
    if not os.path.isfile(p):
        return None
    return int(open(p).read().strip())


# t1: counter file missing -> created at 1, returns ok_result (below threshold)
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "5"
    src = os.path.join(td, "policy.md")
    with open(src, "w") as f:
        f.write("POLICY\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r != {"type": "ok"}:
        fail(f"t1: expected ok, got {r!r}")
    elif read_counter(td) != 1:
        fail(f"t1: counter not created at 1; got {read_counter(td)!r}")
    else:
        ok("t1: missing counter created at 1, returns ok")
    del os.environ["RABBIT_TEST_THRESH"]

# t2: counter below threshold -> incremented, ok
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "5"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("2")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "ok"} and read_counter(td) == 3:
        ok("t2: below threshold: counter incremented, ok returned")
    else:
        fail(f"t2: result={r!r}, counter={read_counter(td)!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t3: counter reaches threshold -> reset to 0, returns [print_result, inject_result]
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "5"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("4")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY-TEXT\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    expected = [
        {"type": "print", "text": "policy refreshed (every 5 prompts)", "icon": "🔄", "color": "green"},
        {"type": "inject", "content": "POLICY-TEXT\n"},
    ]
    if r == expected and read_counter(td) == 0:
        ok("t3: at threshold (4+1=5): reset to 0 and [print, inject] list returned")
    else:
        fail(f"t3: result={r!r}, counter={read_counter(td)!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t4: source is a directory -> concat every *.md in alphabetical order; list shape preserved
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "1"
    pol = os.path.join(td, "policy")
    os.makedirs(pol)
    with open(os.path.join(pol, "b.md"), "w") as f:
        f.write("BBB\n")
    with open(os.path.join(pol, "a.md"), "w") as f:
        f.write("AAA\n")
    with open(os.path.join(pol, "ignored.txt"), "w") as f:
        f.write("nope\n")
    # counter missing -> increments to 1, hits threshold 1 -> refresh
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy", repo_root=td
    )
    expected = [
        {"type": "print", "text": "policy refreshed (every 1 prompts)", "icon": "🔄", "color": "green"},
        {"type": "inject", "content": "AAA\nBBB\n"},
    ]
    if r == expected:
        ok("t4: directory source: [print, inject] returned with concat content")
    else:
        fail(f"t4: unexpected: {r!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t5: missing env var -> default threshold 20
with tempfile.TemporaryDirectory() as td:
    if "RABBIT_TEST_THRESH" in os.environ:
        del os.environ["RABBIT_TEST_THRESH"]
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("18")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("P\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "ok"} and read_counter(td) == 19:
        ok("t5: missing env var: default threshold 20 honored (18 -> 19, no refresh)")
    else:
        fail(f"t5: result={r!r}, counter={read_counter(td)!r}")

# t6: non-int env var -> falls back to default 20
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "not-an-int"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("18")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("P\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "ok"} and read_counter(td) == 19:
        ok("t6: non-int env var falls back to default 20")
    else:
        fail(f"t6: result={r!r}, counter={read_counter(td)!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t7: missing source file -> error_result
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "1"
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "missing.md", repo_root=td
    )
    if r.get("type") == "error":
        ok("t7: missing source returns error_result")
    else:
        fail(f"t7: expected error, got {r!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t8: at-threshold returns list of exactly 2 entries, print THEN inject, with
# payload field shapes correct (text contains "policy refreshed (every", icon
# "🔄", color "green"; inject content is the policy block).
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "3"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("2")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("BLOCK\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if not isinstance(r, list):
        fail(f"t8: expected list, got {type(r).__name__}: {r!r}")
    elif len(r) != 2:
        fail(f"t8: expected list of length 2, got length {len(r)}: {r!r}")
    elif r[0].get("type") != "print":
        fail(f"t8: expected r[0].type=='print', got {r[0]!r}")
    elif r[1].get("type") != "inject":
        fail(f"t8: expected r[1].type=='inject', got {r[1]!r}")
    elif "policy refreshed (every" not in r[0].get("text", ""):
        fail(f"t8: print text missing 'policy refreshed (every': {r[0]!r}")
    elif r[0].get("icon") != "🔄":
        fail(f"t8: expected icon '🔄', got {r[0].get('icon')!r}")
    elif r[0].get("color") != "green":
        fail(f"t8: expected color 'green', got {r[0].get('color')!r}")
    elif r[1].get("content") != "BLOCK\n":
        fail(f"t8: inject content mismatch: {r[1]!r}")
    else:
        ok("t8: at-threshold list shape: [print, inject] with correct payload fields")
    del os.environ["RABBIT_TEST_THRESH"]

# t9: list shape preserved when policy_source is a directory (multi-file source)
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "2"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("1")
    pol = os.path.join(td, "policy")
    os.makedirs(pol)
    with open(os.path.join(pol, "a.md"), "w") as f:
        f.write("A\n")
    with open(os.path.join(pol, "b.md"), "w") as f:
        f.write("B\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy", repo_root=td
    )
    if not isinstance(r, list) or len(r) != 2:
        fail(f"t9: expected list of length 2 for directory source; got {r!r}")
    elif r[0].get("type") != "print" or r[1].get("type") != "inject":
        fail(f"t9: expected [print, inject] ordering; got {r!r}")
    elif r[1].get("content") != "A\nB\n":
        fail(f"t9: directory concat mismatch in inject content: {r!r}")
    elif "policy refreshed (every 2 prompts)" not in r[0].get("text", ""):
        fail(f"t9: expected threshold N=2 in print text; got {r[0]!r}")
    else:
        ok("t9: directory source preserves [print, inject] list shape")
    del os.environ["RABBIT_TEST_THRESH"]

if FAIL:
    print("test-runtime-check-counter-threshold-refresh: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-counter-threshold-refresh: all checks passed.")
