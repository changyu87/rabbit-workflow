#!/usr/bin/env python3
"""test-spec-path-dual-read.py — issue #399 Phase 1 (coexistence window, #450 Pattern 1)

End-to-end regression test for dual-read spec/contract path resolution in
contract.lib.checks. Phase 1 of the docs/spec/ -> specs/ migration makes
contract prefer specs/<name> and fall back to docs/spec/<name>, so every
feature stays green while features migrate one-by-one.

Asserts:
  - resolve_spec_path helper exists, prefers specs/, falls back to docs/spec/.
  - validate_feature does NOT report "missing ... spec.md/contract.md" when a
    feature carries specs/spec.md + specs/contract.md (preferred layout).
  - validate_feature still accepts the legacy docs/spec/ layout (fallback).
  - check_invariant_monotonic_order reads spec.md from specs/ (preferred) and
    from docs/spec/ (fallback), flagging non-monotonic numbering in both.

Run non-interactively. Exits non-zero on failure.
"""

import importlib.util
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")

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
    spec = importlib.util.spec_from_file_location("contract_lib_checks_dualread", CHECKS_PATH)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


checks = load_checks()
if checks is None:
    print("FAIL: could not import lib/checks.py", file=sys.stderr)
    sys.exit(1)


# t1: resolve_spec_path helper exists and is callable.
if hasattr(checks, "resolve_spec_path") and callable(checks.resolve_spec_path):
    ok("t1", "resolve_spec_path exists and is callable")
else:
    fail("t1", "resolve_spec_path missing or not callable")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)


# t2: resolve_spec_path prefers specs/ when present.
with tempfile.TemporaryDirectory() as tmp:
    write(os.path.join(tmp, "specs", "spec.md"), "x")
    write(os.path.join(tmp, "docs", "spec", "spec.md"), "y")
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    if os.path.normpath(resolved) == os.path.normpath(os.path.join(tmp, "specs", "spec.md")):
        ok("t2", "resolve_spec_path prefers specs/ over docs/spec/")
    else:
        fail("t2", f"expected specs/ path, got {resolved}")

# t3: resolve_spec_path falls back to docs/spec/ when specs/ absent.
with tempfile.TemporaryDirectory() as tmp:
    write(os.path.join(tmp, "docs", "spec", "contract.md"), "y")
    resolved = checks.resolve_spec_path(tmp, "contract.md")
    if os.path.normpath(resolved) == os.path.normpath(os.path.join(tmp, "docs", "spec", "contract.md")):
        ok("t3", "resolve_spec_path falls back to docs/spec/ for contract.md")
    else:
        fail("t3", f"expected docs/spec/ fallback, got {resolved}")

# t4: resolve_spec_path returns the docs/spec/ candidate when neither exists
# (so downstream existence checks still report the legacy path consistently).
with tempfile.TemporaryDirectory() as tmp:
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    if os.path.isabs(resolved) and resolved.endswith(os.path.join("spec.md")):
        ok("t4", "resolve_spec_path returns a spec.md candidate when neither layout exists")
    else:
        fail("t4", f"unexpected resolve result for absent layout: {resolved}")


def _spec_errors(result):
    """Subset of validate_feature messages that concern spec/contract files."""
    return [m for m in result.messages
            if ("spec.md" in m or "contract.md" in m) and "ERROR" in m]


# t5 (E2E): validate_feature on a feature whose specs/ carries spec.md +
# contract.md but which has NO docs/spec/ at all must NOT emit a
# missing/empty spec.md or contract.md error.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat-specs")
    write(os.path.join(fdir, "feature.json"), "{}")
    write(os.path.join(fdir, "specs", "spec.md"), "# spec\n")
    write(os.path.join(fdir, "specs", "contract.md"), "# contract\n")
    res = checks.validate_feature(fdir)
    spec_errs = _spec_errors(res)
    if not spec_errs:
        ok("t5", "validate_feature accepts specs/ layout (no spec/contract file errors)")
    else:
        fail("t5", f"specs/ layout still flagged: {spec_errs}")

# t6 (E2E): validate_feature on the legacy docs/spec/ layout must still be
# accepted (fallback path) — no spec/contract file errors.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat-docs-spec")
    write(os.path.join(fdir, "feature.json"), "{}")
    write(os.path.join(fdir, "docs", "spec", "spec.md"), "# spec\n")
    write(os.path.join(fdir, "docs", "spec", "contract.md"), "# contract\n")
    res = checks.validate_feature(fdir)
    spec_errs = _spec_errors(res)
    if not spec_errs:
        ok("t6", "validate_feature accepts legacy docs/spec/ layout (fallback)")
    else:
        fail("t6", f"docs/spec/ layout flagged: {spec_errs}")

# t7 (E2E): validate_feature with NEITHER layout must still flag the missing
# spec.md / contract.md (dual-read must not mask genuine absence).
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat-none")
    write(os.path.join(fdir, "feature.json"), "{}")
    res = checks.validate_feature(fdir)
    spec_errs = _spec_errors(res)
    if any("spec.md" in m for m in spec_errs) and any("contract.md" in m for m in spec_errs):
        ok("t7", "validate_feature still flags missing spec.md + contract.md when neither layout exists")
    else:
        fail("t7", f"missing-spec absence not flagged: {res.messages}")


# Non-monotonic spec body used for t8/t9.
NONMONO = (
    "# spec\n"
    "\n"
    "## Invariants\n"
    "\n"
    "2. second\n"
    "1. out of order\n"
)

# t8 (E2E): check_invariant_monotonic_order reads spec.md from specs/ (preferred).
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "mono-specs")
    write(os.path.join(fdir, "specs", "spec.md"), NONMONO)
    res = checks.check_invariant_monotonic_order([fdir])
    if not res.passed and any("not monotonic" in m for m in res.messages):
        ok("t8", "monotonic check reads spec.md from specs/ (preferred)")
    else:
        fail("t8", f"specs/ spec.md not read by monotonic check: {res.messages}")

# t9 (E2E): check_invariant_monotonic_order reads spec.md from docs/spec/ (fallback).
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "mono-docs-spec")
    write(os.path.join(fdir, "docs", "spec", "spec.md"), NONMONO)
    res = checks.check_invariant_monotonic_order([fdir])
    if not res.passed and any("not monotonic" in m for m in res.messages):
        ok("t9", "monotonic check reads spec.md from docs/spec/ (fallback)")
    else:
        fail("t9", f"docs/spec/ spec.md not read by monotonic check: {res.messages}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
