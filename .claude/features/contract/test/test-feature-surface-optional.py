#!/usr/bin/env python3
"""test-feature-surface-optional.py — issue #468.

`surface` is retired as the source of truth for a feature's published
artifacts; `manifest` is now the single operational source. This test pins
the deprecation semantics: `surface` is NO LONGER REQUIRED by either the
JSON schema or `validate_feature`, while features that still carry `surface`
continue to validate (backwards-compatible deprecation).

End-to-end coverage:
  - schema `required` list does NOT include `surface`.
  - `validate_feature` (library) passes on a feature dir whose feature.json
    has `manifest` but NO `surface`.
  - `validate-feature.py` (CLI shim) exits 0 on the same fixture.
  - a feature carrying BOTH `manifest` and `surface` still validates.

Run non-interactively. Exits non-zero on failure.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA = os.path.join(FEATURE_DIR, "schemas", "feature.json.schema.json")
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")
VALIDATE = os.path.join(FEATURE_DIR, "scripts", "validate-feature.py")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def load_checks():
    spec = importlib.util.spec_from_file_location("contract_lib_checks_468", CHECKS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_feature(d, *, with_surface, with_manifest):
    """Build a structurally-valid feature dir; surface/manifest toggled."""
    name = os.path.basename(d)
    os.makedirs(os.path.join(d, "specs"), exist_ok=True)
    os.makedirs(os.path.join(d, "test"), exist_ok=True)
    with open(os.path.join(d, "specs", "spec.md"), "w") as f:
        f.write("# Fixture spec\nBody.\n")
    with open(os.path.join(d, "specs", "contract.md"), "w") as f:
        f.write("# Fixture contract\nBody.\n")
    run_py = os.path.join(d, "test", "run.py")
    with open(run_py, "w") as f:
        f.write("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n")
    os.chmod(run_py, 0o755)

    data = {
        "name": name,
        "version": "0.1.0",
        "owner": "test-owner",
        "tdd_state": "spec",
        "summary": "Fixture for issue #468 surface-optional test.",
        "deprecation_criterion": "when test is done",
    }
    if with_manifest:
        data["manifest"] = []
    if with_surface:
        data["surface"] = {"hooks": [], "commands": [], "agents": [], "skills": []}
    with open(os.path.join(d, "feature.json"), "w") as f:
        json.dump(data, f, indent=2)


# t1: schema MUST NOT require `surface`.
with open(SCHEMA) as f:
    schema = json.load(f)
required = schema.get("required", [])
if "surface" in required:
    fail("t1", f"'surface' is still in schema required (got {required})")
else:
    ok("t1", "schema does not require 'surface'")

# t2: library validate_feature passes on a feature with manifest, no surface.
checks = load_checks()
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat_no_surface")
    make_feature(fdir, with_surface=False, with_manifest=True)
    res = checks.validate_feature(fdir)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t2", "validate_feature passes on manifest-only feature (no surface)")
    else:
        fail("t2", f"expected passed=True, got {res!r}")

# t3: CLI shim exits 0 on the same manifest-only fixture (end-to-end).
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat_no_surface_cli")
    make_feature(fdir, with_surface=False, with_manifest=True)
    r = subprocess.run(["python3", VALIDATE, fdir], capture_output=True, text=True)
    if r.returncode == 0:
        ok("t3", "validate-feature.py CLI exits 0 on manifest-only feature")
    else:
        fail("t3", f"shim returned {r.returncode}; stdout={r.stdout!r} stderr={r.stderr!r}")

# t4: backwards-compatible — a feature carrying BOTH surface and manifest still validates.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat_both")
    make_feature(fdir, with_surface=True, with_manifest=True)
    res = checks.validate_feature(fdir)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t4", "validate_feature still passes when both surface and manifest present")
    else:
        fail("t4", f"expected passed=True, got {res!r}")

# t5: a feature with neither surface nor manifest still validates (surface no
# longer mandatory; manifest is optional per Inv 35).
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat_neither")
    make_feature(fdir, with_surface=False, with_manifest=False)
    res = checks.validate_feature(fdir)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t5", "validate_feature passes with neither surface nor manifest")
    else:
        fail("t5", f"expected passed=True, got {res!r}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
