#!/usr/bin/env python3
"""test-reflow-invariants.py — deterministic reflow tool (#724).

End-to-end test for contract.lib.reflow.reflow_feature and its CLI shim
scripts/reflow-invariants.py.

NOTE: the invariant numbers in this file's FIXTURE strings are built at
runtime from integer variables (never as bare `Inv N` literals), so a future
reflow of the contract feature does NOT rewrite this test's fixtures.

Cases (hermetic — fixture feature trees in a tmp dir):
  t1  reflow_feature renumbers a gapped spec to contiguous 1..N (leading
      list numbers rewritten in spec.md).
  t2  Live cross-references in spec.md / contract.md / test files are
      remapped in ONE pass.
  t3  A reference to a RETIRED (gap) invariant number is LEFT UNTOUCHED.
  t4  docs/CHANGELOG.md is NEVER rewritten.
  t5  Suffix references remap the integer, keep the suffix.
  t6  Single atomic pass: no cascade double-mapping.
  t7  Re-running reflow on an already-contiguous feature is a no-op.
  t8  CLI shim exists, is executable, and --dry-run writes nothing.

Non-interactive. Exits non-zero on any failure.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REFLOW_PATH = os.path.join(FEATURE_DIR, "lib", "reflow.py")
SHIM_PATH = os.path.join(FEATURE_DIR, "scripts", "reflow-invariants.py")

# Build "Inv N" tokens from integers so this source file carries no bare
# `Inv <number>` literal that a contract reflow would rewrite.
def inv(n, suffix=""):
    return "Inv " + str(n) + suffix

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


def load_reflow():
    sys.path.insert(0, FEATURE_DIR)
    spec = importlib.util.spec_from_file_location("contract_lib_reflow", REFLOW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fixture(root):
    """Feature with live invariants 1,2,5,8 (gaps at 3,4,6,7), cross-refs to
    live (5,8) and retired (6) numbers, plus a CHANGELOG tombstone.
    """
    feat = os.path.join(root, "fixture-feat")
    docs = os.path.join(feat, "docs")
    test = os.path.join(feat, "test")
    os.makedirs(docs)
    os.makedirs(test)
    spec = (
        "# F\n\n## Invariants\n\n"
        "1. first.\n"
        "2. second.\n"
        f"5. fifth, see {inv(8)} and the retired {inv(6)}.\n"
        f"8. eighth, mentions {inv(5)} and {inv(8,'a')}.\n"
    )
    with open(os.path.join(docs, "spec.md"), "w") as f:
        f.write(spec)
    with open(os.path.join(docs, "contract.md"), "w") as f:
        f.write(f"Boundary. See {inv(8)} for the surface.\n")
    with open(os.path.join(docs, "CHANGELOG.md"), "w") as f:
        f.write(f"History: {inv(8)} tombstone; {inv(5)} note.\n")
    with open(os.path.join(test, "test-x.py"), "w") as f:
        f.write(f"# asserts {inv(5)} holds and {inv(8)} too; retired {inv(6)}.\n")
    with open(os.path.join(feat, "feature.json"), "w") as f:
        json.dump({"name": "fixture-feat", "version": "1.0.0"}, f)
    return feat


reflow = load_reflow()

with tempfile.TemporaryDirectory() as tmp:
    feat = make_fixture(tmp)
    res = reflow.reflow_feature(feat, dry_run=False)
    spec_after = open(os.path.join(feat, "docs", "spec.md")).read()
    contract_after = open(os.path.join(feat, "docs", "contract.md")).read()
    changelog_after = open(os.path.join(feat, "docs", "CHANGELOG.md")).read()
    test_after = open(os.path.join(feat, "test", "test-x.py")).read()

    # t1: map and contiguous leading numbers
    if res.renumber_map == {5: 3, 8: 4}:
        ok("t1", f"renumber map is {res.renumber_map}")
    else:
        ko("t1", f"renumber map wrong: {res.renumber_map}")
    lead = [ln.split(".")[0] for ln in spec_after.splitlines() if ln[:1].isdigit()]
    if lead == ["1", "2", "3", "4"]:
        ok("t1b", "spec.md leading numbers contiguous 1,2,3,4")
    else:
        ko("t1b", f"leading numbers not contiguous: {lead}")

    # t2: live refs remapped 8->4, 5->3
    if inv(4) in contract_after and inv(8) not in contract_after:
        ok("t2", "contract.md cross-ref 8 -> 4")
    else:
        ko("t2", f"contract.md not remapped: {contract_after!r}")
    if inv(3) in test_after and inv(4) in test_after and inv(5) not in test_after \
            and inv(8) not in test_after:
        ok("t2b", "test file cross-refs remapped (5->3, 8->4)")
    else:
        ko("t2b", f"test file not remapped: {test_after!r}")

    # t3: retired 6 untouched
    if inv(6) in spec_after and inv(6) in test_after:
        ok("t3", "retired number 6 reference left untouched")
    else:
        ko("t3", f"retired 6 wrongly remapped: spec={spec_after!r} test={test_after!r}")

    # t4: CHANGELOG never rewritten
    if changelog_after == f"History: {inv(8)} tombstone; {inv(5)} note.\n":
        ok("t4", "CHANGELOG.md left untouched")
    else:
        ko("t4", f"CHANGELOG was rewritten: {changelog_after!r}")

    # t5: suffix 8a -> 4a
    if inv(4, "a") in spec_after and inv(8, "a") not in spec_after:
        ok("t5", "suffix reference 8a -> 4a (suffix preserved)")
    else:
        ko("t5", f"suffix not remapped: {spec_after!r}")

# t6: cascade safety — live 1,3,8 -> map {3:2, 8:3}. The old ref to 8 must
# become 3, the old ref to 3 must become 2; never 8->3->2 double-mapping.
with tempfile.TemporaryDirectory() as tmp:
    feat = os.path.join(tmp, "cascade-feat")
    docs = os.path.join(feat, "docs")
    os.makedirs(docs)
    with open(os.path.join(docs, "spec.md"), "w") as f:
        f.write(
            "# F\n\n## Invariants\n\n"
            "1. one.\n"
            f"3. three, see {inv(8)}.\n"
            f"8. eight, see {inv(3)}.\n"
        )
    with open(os.path.join(feat, "feature.json"), "w") as f:
        json.dump({"name": "cascade-feat", "version": "1.0.0"}, f)
    res = reflow.reflow_feature(feat, dry_run=False)
    spec_after = open(os.path.join(docs, "spec.md")).read()
    if res.renumber_map == {3: 2, 8: 3} \
            and spec_after.count("see " + inv(3)) == 1 \
            and spec_after.count("see " + inv(2)) == 1:
        ok("t6", "single atomic pass — no cascade double-mapping")
    else:
        ko("t6", f"cascade bug: map={res.renumber_map} spec={spec_after!r}")

# t7: already-contiguous no-op
with tempfile.TemporaryDirectory() as tmp:
    feat = os.path.join(tmp, "contig-feat")
    docs = os.path.join(feat, "docs")
    os.makedirs(docs)
    with open(os.path.join(docs, "spec.md"), "w") as f:
        f.write("# F\n\n## Invariants\n\n1. one.\n2. two.\n3. three.\n")
    with open(os.path.join(feat, "feature.json"), "w") as f:
        json.dump({"name": "contig-feat", "version": "1.0.0"}, f)
    res = reflow.reflow_feature(feat, dry_run=False)
    if res.ok and not res.renumber_map and not res.files_changed:
        ok("t7", "already-contiguous feature is a no-op")
    else:
        ko("t7", f"no-op expected: map={res.renumber_map} changed={res.files_changed}")

# t8: CLI shim exists, executable, --dry-run writes nothing
if not os.path.isfile(SHIM_PATH):
    ko("t8a", f"CLI shim missing: {SHIM_PATH}")
else:
    ok("t8a", "CLI shim exists")
    if os.access(SHIM_PATH, os.X_OK):
        ok("t8b", "CLI shim is executable")
    else:
        ko("t8b", "CLI shim not executable")
    with tempfile.TemporaryDirectory() as tmp:
        feat = make_fixture(tmp)
        before = open(os.path.join(feat, "docs", "spec.md")).read()
        r = subprocess.run(
            ["python3", SHIM_PATH, feat, "--dry-run"],
            capture_output=True, text=True,
        )
        after = open(os.path.join(feat, "docs", "spec.md")).read()
        if r.returncode == 0 and after == before and "WOULD CHANGE" in r.stdout:
            ok("t8c", "--dry-run reports changes but writes nothing")
        else:
            ko("t8c", f"dry-run failed: rc={r.returncode} changed={after != before}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
