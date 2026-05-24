#!/usr/bin/env python3
"""test-validate-meta-contract-cli.py — exercises the CLI shim:
- exit 0 on valid feature dir
- exit 1 on invalid feature dir (with messages to stderr)
- exit 2 on invocation error (missing argv, non-directory path)
- has module-level docstring (per Inv 16)
"""

import os
import sys
import json
import subprocess
import tempfile

SCRIPT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "validate-meta-contract.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: script exists and is executable
if not os.path.isfile(SCRIPT):
    fail(f"script missing: {SCRIPT}")
    sys.exit(1)
ok("script exists")
if not os.access(SCRIPT, os.X_OK):
    fail("script not executable (chmod +x)")
else:
    ok("script is executable")

# t2: has module docstring (per Inv 16)
with open(SCRIPT) as f:
    src = f.read()
first_lines = "\n".join(src.split("\n")[:5])
if '"""' not in first_lines:
    fail("script missing module-level docstring near top of file (per Inv 16)")
else:
    ok("script has module-level docstring")

# t3: missing argv -> exit 2
res = subprocess.run(["python3", SCRIPT], capture_output=True, text=True)
if res.returncode != 2:
    fail(f"missing-argv expected exit 2, got {res.returncode}; stderr={res.stderr!r}")
else:
    ok("missing argv -> exit 2")

# t4: non-directory path -> exit 2
res = subprocess.run(["python3", SCRIPT, "/nonexistent/path"], capture_output=True, text=True)
if res.returncode != 2:
    fail(f"non-directory expected exit 2, got {res.returncode}")
else:
    ok("non-directory -> exit 2")

# t5: valid feature dir -> exit 0
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "feature.json"), "w") as f:
        json.dump({"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                   "manifest": [{"api": "publish_skill", "args": {"source": "x"}}]}, f)
    res = subprocess.run(["python3", SCRIPT, td], capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"valid feature expected exit 0, got {res.returncode}; stderr={res.stderr!r}")
    else:
        ok("valid feature dir -> exit 0")

# t6: invalid feature dir -> exit 1 with stderr message
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "feature.json"), "w") as f:
        json.dump({"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                   "manifest": [{"api": "publish_bogus", "args": {}}]}, f)
    res = subprocess.run(["python3", SCRIPT, td], capture_output=True, text=True)
    if res.returncode != 1:
        fail(f"invalid feature expected exit 1, got {res.returncode}")
    elif "unknown publish api" not in res.stderr:
        fail(f"invalid feature did not surface error to stderr: {res.stderr!r}")
    else:
        ok("invalid feature dir -> exit 1 with error on stderr")

if FAIL:
    print("test-validate-meta-contract-cli: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-cli: all checks passed.")
