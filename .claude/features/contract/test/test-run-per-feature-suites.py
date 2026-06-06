#!/usr/bin/env python3
"""test-run-per-feature-suites.py — Inv 66.

Cross-feature per-feature-suite gate. The contract repo-gate (test/run.py)
historically ran ONLY cross-feature contract checks; it did NOT run each
feature's own test/run.py suite. So a change in feature A that REDS feature
B's per-feature suite landed undetected — A's TDD subagent runs only A's
suite, and the contract gate never touched B's. This test pins the new gate
check that discovers every feature's `.claude/features/<name>/test/run.py`
and RUNS each, failing the gate if any per-feature suite reds.

The behaviour is owned by the reusable `contract.lib.feature_suites` helpers,
which the gate check (this file) and any future caller share. The helpers are
isolated against a TEMP features layout so RED/GREEN is fast and deterministic
— they never depend on the real tree for the RED case.

  t1: helper discovers every feature's test/run.py in a temp layout and runs
      each; a layout where ALL stub suites exit 0 yields all-pass.
  t2: a temp layout containing ONE deliberately-failing stub suite (exit 1)
      makes the helper report that feature FAILED, naming the failing feature.
  t3: the helper enumerates features deterministically (sorted by name) and
      a feature dir lacking test/run.py is skipped (not an error).
  t4: the helper does NOT re-invoke contract's own test/run.py (no infinite
      recursion): pointed at the REAL features root, contract is excluded
      from the suites it discovers.
  t5: end-to-end against the REAL repo — every real per-feature suite is GREEN,
      so the gate check passes (the live gate assertion; a pre-existing
      per-feature red surfaces here).
"""

import os
import stat
import subprocess
import sys
import tempfile
import importlib.util

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
LIB = os.path.join(FEATURE_DIR, "lib", "feature_suites.py")

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS t{n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    FAIL += 1


def repo_root():
    result = subprocess.run(
        ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))


spec = importlib.util.spec_from_file_location("contract_feature_suites", LIB)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
run_feature_suites = mod.run_feature_suites
discover_feature_suites = mod.discover_feature_suites


def make_stub_feature(features_root, name, exit_code):
    fdir = os.path.join(features_root, name, "test")
    os.makedirs(fdir, exist_ok=True)
    run_py = os.path.join(fdir, "run.py")
    with open(run_py, "w") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            f"import sys; sys.exit({exit_code})\n"
        )
    os.chmod(run_py, os.stat(run_py).st_mode | stat.S_IXUSR)


def make_feature_no_suite(features_root, name):
    os.makedirs(os.path.join(features_root, name, "scripts"), exist_ok=True)


# t1: all-green temp layout -> all pass
with tempfile.TemporaryDirectory() as tmp:
    make_stub_feature(tmp, "feat_a", 0)
    make_stub_feature(tmp, "feat_b", 0)
    results = run_feature_suites(tmp)
    names = {name for name, _passed, _out in results}
    all_pass = all(passed for _name, passed, _out in results)
    if names == {"feat_a", "feat_b"} and all_pass:
        ok(1, "all-green temp layout: both stub suites discovered and passed")
    else:
        fail_t(1, f"expected feat_a+feat_b all-pass; got {results!r}")

# t2: one failing stub -> that feature reported FAILED
with tempfile.TemporaryDirectory() as tmp:
    make_stub_feature(tmp, "feat_a", 0)
    make_stub_feature(tmp, "feat_bad", 1)
    results = run_feature_suites(tmp)
    failed = [name for name, passed, _out in results if not passed]
    if failed == ["feat_bad"]:
        ok(2, "one failing stub suite is reported as the sole FAILED feature")
    else:
        fail_t(2, f"expected only feat_bad failed; got failed={failed}, all={results!r}")

# t3: deterministic ordering + a feature without test/run.py is skipped
with tempfile.TemporaryDirectory() as tmp:
    make_stub_feature(tmp, "zeta", 0)
    make_stub_feature(tmp, "alpha", 0)
    make_feature_no_suite(tmp, "no_suite")
    results = run_feature_suites(tmp)
    ordered_names = [name for name, _p, _o in results]
    if ordered_names == ["alpha", "zeta"]:
        ok(3, "features enumerated deterministically (sorted); no-suite dir skipped")
    else:
        fail_t(3, f"expected ['alpha','zeta']; got {ordered_names}")

# t4: pointed at the real features root, contract is NOT among the discovered
#     suites (no infinite recursion into contract's own test/run.py)
ROOT = repo_root()
real_features_root = os.path.join(ROOT, ".claude", "features")
discovered = discover_feature_suites(real_features_root)
discovered_names = [name for name, _path in discovered]
if "contract" not in discovered_names:
    ok(4, "contract excluded from discovered per-feature suites (no recursion)")
else:
    fail_t(4, f"contract MUST be excluded from per-feature suites; got {discovered_names}")

# t5: live gate — every real per-feature suite is GREEN
results = run_feature_suites(real_features_root)
reds = [name for name, passed, _out in results if not passed]
if not reds:
    ok(5, f"all {len(results)} real per-feature suites are GREEN")
else:
    detail = []
    for name, passed, out in results:
        if not passed:
            detail.append(f"--- {name} ---\n{out[-800:]}")
    fail_t(5, "pre-existing per-feature red(s): " + ", ".join(reds)
              + "\n" + "\n".join(detail))

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
