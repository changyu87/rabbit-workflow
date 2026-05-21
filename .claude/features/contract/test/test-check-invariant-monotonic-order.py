#!/usr/bin/env python3
"""test-check-invariant-monotonic-order.py — Inv 38 / CONTRACT-BACKLOG-30.

End-to-end test for the cross-feature invariant-monotonic-order check:

  t1  contract.lib.checks exports check_invariant_monotonic_order callable.
  t2  Function returns CheckResult.
  t3  Running it on the live set of feature dirs under .claude/features/
      (every entry that has docs/spec/spec.md) returns passed=True,
      thanks to the KNOWN_ISSUES allowlist for features pending renumber.
  t4  CLI shim scripts/enforcement/check-invariant-monotonic-order.py
      exists, is executable, and exits 0 on the same live input.
  t5  A synthetic feature dir with a deliberately non-monotonic
      Invariants section (1 -> 5 -> 3) and NOT in KNOWN_ISSUES is
      reported as a failure with a diagnostic message.

Non-interactive. Exits non-zero on any failure.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")
SHIM_PATH = os.path.join(
    FEATURE_DIR, "scripts", "enforcement", "check-invariant-monotonic-order.py"
)
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def load_checks():
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks_inv_mono", CHECKS_PATH
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_feature_dirs():
    dirs = []
    for entry in sorted(os.listdir(FEATURES_ROOT)):
        full = os.path.join(FEATURES_ROOT, entry)
        if not os.path.isdir(full):
            continue
        if os.path.isfile(os.path.join(full, "docs", "spec", "spec.md")):
            dirs.append(full)
    return dirs


checks = load_checks()
if checks is None:
    ko("t0", f"could not import {CHECKS_PATH}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)

# t1
if hasattr(checks, "check_invariant_monotonic_order") and callable(
    checks.check_invariant_monotonic_order
):
    ok("t1", "check_invariant_monotonic_order exported and callable")
else:
    ko("t1", "check_invariant_monotonic_order missing or not callable")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)

# t2 + t3: live feature dirs pass (KNOWN_ISSUES covers the three pending)
dirs = live_feature_dirs()
result = checks.check_invariant_monotonic_order(dirs)
if not hasattr(result, "passed") or not hasattr(result, "messages"):
    ko("t2", f"return value is not a CheckResult: {result!r}")
else:
    ok("t2", "returns CheckResult")
    if result.passed:
        ok("t3", f"live feature set ({len(dirs)} dirs) passes monotonic check")
    else:
        ko(
            "t3",
            "live feature set fails monotonic check:\n    "
            + "\n    ".join(result.messages),
        )

# t4: CLI shim exists, executable, exits 0
if not os.path.isfile(SHIM_PATH):
    ko("t4a", f"CLI shim missing: {SHIM_PATH}")
else:
    ok("t4a", "CLI shim exists")
    if not os.access(SHIM_PATH, os.X_OK):
        ko("t4b", f"CLI shim not executable: {SHIM_PATH}")
    else:
        ok("t4b", "CLI shim is executable")
    r = subprocess.run(
        ["python3", SHIM_PATH, *dirs],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        ok("t4c", "CLI shim exits 0 on live feature set")
    else:
        ko(
            "t4c",
            f"CLI shim exited {r.returncode}; stdout={r.stdout!r}; stderr={r.stderr!r}",
        )

# t5: synthetic non-monotonic spec is reported as failure
with tempfile.TemporaryDirectory() as tmp:
    fake_feat = os.path.join(tmp, "fake-monotonic-violator")
    spec_dir = os.path.join(fake_feat, "docs", "spec")
    os.makedirs(spec_dir)
    with open(os.path.join(spec_dir, "spec.md"), "w") as f:
        f.write(
            "# Fake feature\n\n"
            "## Invariants\n\n"
            "1. first item.\n"
            "5. fifth, skipped ahead (allowed jump up).\n"
            "3. third, back-step (NOT monotonic — must be flagged).\n"
        )
    res = checks.check_invariant_monotonic_order([fake_feat])
    if res.passed:
        ko("t5", f"synthetic violator was not flagged; messages={res.messages}")
    else:
        joined = "\n".join(res.messages)
        if "fake-monotonic-violator" in joined and "5" in joined and "3" in joined:
            ok("t5", "synthetic 1->5->3 spec is flagged with feature+numbers in diagnostic")
        else:
            ko(
                "t5",
                f"synthetic violator flagged but diagnostic incomplete: {res.messages}",
            )

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
