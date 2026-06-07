#!/usr/bin/env python3
"""test-docs-layout-dual-read.py — flat docs/ layout dual-read coexistence.

End-to-end test for the contract feature's spec/contract/CHANGELOG path
resolution accepting BOTH the flat docs/ layout (docs/spec.md,
docs/contract.md, docs/CHANGELOG.md) and the current specs/ layout
(specs/spec.md, specs/contract.md, <feature>/CHANGELOG.md), PREFERRING
docs/ and FALLING BACK to the current location.

This is the additive opening half of the specs/ -> docs/ flatten
coexistence window: no files are moved; every real feature stays on
specs/, so the full suite stays green while resolvers accept either layout.

Asserts (each maps to an acceptance criterion):
  t1  resolve_spec_path resolves docs/spec.md when only docs/ is present.
  t2  resolve_spec_path falls back to specs/spec.md when only specs/ is
      present (current-location fallback preserved).
  t3  when BOTH docs/spec.md and specs/spec.md exist, docs/ wins.
  t4  resolve_spec_path returns the specs/ candidate when neither layout
      exists (canonical-path-for-error-message behavior preserved).
  t5  a sibling docs/bugs/ directory is preserved/ignored: resolution of
      docs/spec.md is unaffected by docs/bugs/, and never targets it.
  t6  resolve_changelog_path resolves docs/CHANGELOG.md when present.
  t7  resolve_changelog_path falls back to <feature>/CHANGELOG.md (the
      current root location) when docs/ is absent.
  t8  resolve_changelog_path: docs/ wins when both exist.
  t9  (E2E) validate_feature accepts the flat docs/ layout (no spec/
      contract file errors) for spec.md + contract.md under docs/.
  t10 (E2E) validate_feature still accepts the current specs/ layout
      (fallback preserved).
  t11 (E2E) validate_feature: docs/ wins — a feature with docs/spec.md +
      docs/contract.md validates even if specs/ is empty/absent.
  t12 (E2E) check_invariant_monotonic_order reads spec.md from docs/ (a
      non-monotonic docs/spec.md is flagged).
  t13 (E2E) check_invariant_monotonic_order still reads spec.md from
      specs/ (fallback preserved).
  t14 (E2E) check_invariant_monotonic_order: docs/ wins — a monotonic
      docs/spec.md masks a non-monotonic specs/spec.md (docs preferred).

Non-interactive. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the specs/ -> docs/ flatten coexistence window
closes (the specs/ fallback is dropped) — this test folds into the
single-read docs/ layout regression at that point.
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
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks_docslayout", CHECKS_PATH
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def norm(p):
    return os.path.normpath(p)


checks = load_checks()
if checks is None:
    print("FAIL: could not import lib/checks.py", file=sys.stderr)
    sys.exit(1)


# ---- resolve_spec_path: flat docs/ preference + specs/ fallback -------------

# t1: docs/ only -> resolves docs/spec.md.
with tempfile.TemporaryDirectory() as tmp:
    write(os.path.join(tmp, "docs", "spec.md"), "x")
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    if norm(resolved) == norm(os.path.join(tmp, "docs", "spec.md")):
        ok("t1", "resolve_spec_path resolves docs/spec.md when only docs/ present")
    else:
        fail("t1", f"expected docs/ path, got {resolved}")

# t2: specs/ only -> falls back to specs/spec.md.
with tempfile.TemporaryDirectory() as tmp:
    write(os.path.join(tmp, "specs", "spec.md"), "x")
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    if norm(resolved) == norm(os.path.join(tmp, "specs", "spec.md")):
        ok("t2", "resolve_spec_path falls back to specs/spec.md")
    else:
        fail("t2", f"expected specs/ fallback path, got {resolved}")

# t3: both present -> docs/ wins.
with tempfile.TemporaryDirectory() as tmp:
    write(os.path.join(tmp, "docs", "spec.md"), "docs")
    write(os.path.join(tmp, "specs", "spec.md"), "specs")
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    if norm(resolved) == norm(os.path.join(tmp, "docs", "spec.md")):
        ok("t3", "resolve_spec_path prefers docs/ when both layouts present")
    else:
        fail("t3", f"docs/ did not win: got {resolved}")

# t4: neither present -> returns specs/ candidate (canonical-path-for-error).
with tempfile.TemporaryDirectory() as tmp:
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    if norm(resolved) == norm(os.path.join(tmp, "specs", "spec.md")):
        ok("t4", "resolve_spec_path returns specs/ candidate when neither exists")
    else:
        fail("t4", f"expected specs/ candidate, got {resolved}")

# t5: docs/bugs/ sibling preserved/ignored.
with tempfile.TemporaryDirectory() as tmp:
    write(os.path.join(tmp, "docs", "spec.md"), "x")
    os.makedirs(os.path.join(tmp, "docs", "bugs"), exist_ok=True)
    write(os.path.join(tmp, "docs", "bugs", "BUG-x.md"), "ignored")
    resolved = checks.resolve_spec_path(tmp, "spec.md")
    bugs_present = os.path.isdir(os.path.join(tmp, "docs", "bugs"))
    if (norm(resolved) == norm(os.path.join(tmp, "docs", "spec.md"))
            and "bugs" not in norm(resolved).split(os.sep)
            and bugs_present):
        ok("t5", "docs/bugs/ sibling preserved and never targeted by resolution")
    else:
        fail("t5", f"docs/bugs/ handling wrong: resolved={resolved} "
                   f"bugs_present={bugs_present}")


# ---- resolve_changelog_path: docs/CHANGELOG.md + root fallback -------------

if not (hasattr(checks, "resolve_changelog_path")
        and callable(checks.resolve_changelog_path)):
    fail("t6", "resolve_changelog_path missing or not callable")
    fail("t7", "resolve_changelog_path missing or not callable")
    fail("t8", "resolve_changelog_path missing or not callable")
else:
    # t6: docs/CHANGELOG.md present -> resolves it.
    with tempfile.TemporaryDirectory() as tmp:
        write(os.path.join(tmp, "docs", "CHANGELOG.md"), "x")
        resolved = checks.resolve_changelog_path(tmp)
        if norm(resolved) == norm(os.path.join(tmp, "docs", "CHANGELOG.md")):
            ok("t6", "resolve_changelog_path resolves docs/CHANGELOG.md")
        else:
            fail("t6", f"expected docs/ CHANGELOG, got {resolved}")

    # t7: root CHANGELOG.md fallback.
    with tempfile.TemporaryDirectory() as tmp:
        write(os.path.join(tmp, "CHANGELOG.md"), "x")
        resolved = checks.resolve_changelog_path(tmp)
        if norm(resolved) == norm(os.path.join(tmp, "CHANGELOG.md")):
            ok("t7", "resolve_changelog_path falls back to <feature>/CHANGELOG.md")
        else:
            fail("t7", f"expected root CHANGELOG fallback, got {resolved}")

    # t8: both present -> docs/ wins.
    with tempfile.TemporaryDirectory() as tmp:
        write(os.path.join(tmp, "docs", "CHANGELOG.md"), "docs")
        write(os.path.join(tmp, "CHANGELOG.md"), "root")
        resolved = checks.resolve_changelog_path(tmp)
        if norm(resolved) == norm(os.path.join(tmp, "docs", "CHANGELOG.md")):
            ok("t8", "resolve_changelog_path prefers docs/ when both present")
        else:
            fail("t8", f"docs/ CHANGELOG did not win: got {resolved}")


def _spec_errors(result):
    return [m for m in result.messages
            if ("spec.md" in m or "contract.md" in m) and "ERROR" in m]


# ---- validate_feature: dual-read E2E ---------------------------------------

# t9: flat docs/ layout accepted.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat-docs")
    write(os.path.join(fdir, "feature.json"), "{}")
    write(os.path.join(fdir, "docs", "spec.md"), "# spec\n")
    write(os.path.join(fdir, "docs", "contract.md"), "# contract\n")
    res = checks.validate_feature(fdir)
    errs = _spec_errors(res)
    if not errs:
        ok("t9", "validate_feature accepts flat docs/ layout")
    else:
        fail("t9", f"docs/ layout flagged: {errs}")

# t10: specs/ layout still accepted.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat-specs")
    write(os.path.join(fdir, "feature.json"), "{}")
    write(os.path.join(fdir, "specs", "spec.md"), "# spec\n")
    write(os.path.join(fdir, "specs", "contract.md"), "# contract\n")
    res = checks.validate_feature(fdir)
    errs = _spec_errors(res)
    if not errs:
        ok("t10", "validate_feature still accepts specs/ layout (fallback)")
    else:
        fail("t10", f"specs/ layout flagged: {errs}")

# t11: docs/ wins for validate_feature (docs present, specs absent).
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feat-docs-only")
    write(os.path.join(fdir, "feature.json"), "{}")
    write(os.path.join(fdir, "docs", "spec.md"), "# spec\n")
    write(os.path.join(fdir, "docs", "contract.md"), "# contract\n")
    os.makedirs(os.path.join(fdir, "docs", "bugs"), exist_ok=True)
    res = checks.validate_feature(fdir)
    errs = _spec_errors(res)
    if not errs:
        ok("t11", "validate_feature accepts docs/ layout alongside docs/bugs/")
    else:
        fail("t11", f"docs/ layout with docs/bugs/ flagged: {errs}")


# ---- check_invariant_monotonic_order: dual-read E2E ------------------------

NONMONO = (
    "# spec\n\n## Invariants\n\n2. second\n1. out of order\n"
)
MONO = (
    "# spec\n\n## Invariants\n\n1. first\n2. second\n"
)

# t12: monotonic check reads docs/spec.md.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "mono-docs")
    write(os.path.join(fdir, "docs", "spec.md"), NONMONO)
    res = checks.check_invariant_monotonic_order([fdir])
    if not res.passed and any("not monotonic" in m for m in res.messages):
        ok("t12", "monotonic check reads spec.md from docs/")
    else:
        fail("t12", f"docs/ spec.md not read by monotonic check: {res.messages}")

# t13: monotonic check still reads specs/spec.md.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "mono-specs")
    write(os.path.join(fdir, "specs", "spec.md"), NONMONO)
    res = checks.check_invariant_monotonic_order([fdir])
    if not res.passed and any("not monotonic" in m for m in res.messages):
        ok("t13", "monotonic check still reads spec.md from specs/ (fallback)")
    else:
        fail("t13", f"specs/ spec.md not read by monotonic check: {res.messages}")

# t14: docs/ wins — monotonic docs/spec.md masks non-monotonic specs/spec.md.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "mono-both")
    write(os.path.join(fdir, "docs", "spec.md"), MONO)
    write(os.path.join(fdir, "specs", "spec.md"), NONMONO)
    res = checks.check_invariant_monotonic_order([fdir])
    if res.passed and not any("not monotonic" in m for m in res.messages):
        ok("t14", "monotonic check prefers docs/spec.md over specs/spec.md")
    else:
        fail("t14", f"docs/ did not win for monotonic check: {res.messages}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
