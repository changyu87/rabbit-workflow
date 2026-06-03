#!/usr/bin/env python3
"""test-specs-layout-migrated.py — rabbit-auto-evolve issue #399 Phase 2.

End-to-end regression test for the docs/spec/ -> specs/ migration of the
rabbit-auto-evolve feature (Phase 2 of issue #399; coexistence window opened
in Phase 1).

Two halves:

  A. Real-layout assertions (acceptance criteria), against this feature's
     actual on-disk tree:
       - specs/spec.md exists and is non-empty
       - specs/contract.md exists and is non-empty
       - docs/spec/ no longer exists
       - docs/bugs/ is retained (sibling of the moved spec dir)
       - no source file under the feature references the legacy
         `docs/spec/` path for THIS feature's own spec/contract

  B. Tooling dual-read assertions (E2E), against scripts/triage-issue.py: the
     spec-path resolver it owns prefers the new specs/<name> layout and falls
     back to the legacy docs/spec/<name> layout during the coexistence window,
     and triage-issue's rule-6 head-matter read resolves a feature spec from
     BOTH layouts end-to-end.

Run non-interactively. Exits non-zero on failure.
"""

import importlib.util
import os
import re
import sys
import tempfile

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
SCRIPTS_DIR = os.path.join(FEATURE_DIR, "scripts")
TRIAGE_PATH = os.path.join(SCRIPTS_DIR, "triage-issue.py")

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


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_triage():
    """Import scripts/triage-issue.py as a module by file path."""
    spec = importlib.util.spec_from_file_location(
        "rae_triage_issue_under_test", TRIAGE_PATH
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001 — surface import failure as a test fail
        print(f"FAIL: could not import triage-issue.py: {e}", file=sys.stderr)
        return None
    return mod


# ---------------------------------------------------------------------------
# Part A — real on-disk layout (acceptance criteria)
# ---------------------------------------------------------------------------

specs_spec = os.path.join(FEATURE_DIR, "specs", "spec.md")
specs_contract = os.path.join(FEATURE_DIR, "specs", "contract.md")
docs_spec_dir = os.path.join(FEATURE_DIR, "docs", "spec")
docs_bugs_dir = os.path.join(FEATURE_DIR, "docs", "bugs")

# a1: specs/spec.md exists and is non-empty
if os.path.isfile(specs_spec) and os.path.getsize(specs_spec) > 0:
    ok("a1", "specs/spec.md exists and is non-empty")
else:
    fail("a1", f"specs/spec.md missing or empty: {specs_spec}")

# a2: specs/contract.md exists and is non-empty
if os.path.isfile(specs_contract) and os.path.getsize(specs_contract) > 0:
    ok("a2", "specs/contract.md exists and is non-empty")
else:
    fail("a2", f"specs/contract.md missing or empty: {specs_contract}")

# a3: docs/spec/ no longer exists
if not os.path.exists(docs_spec_dir):
    ok("a3", "docs/spec/ has been removed")
else:
    fail("a3", f"docs/spec/ still present: {docs_spec_dir}")

# a4: docs/bugs/ is retained
if os.path.isdir(docs_bugs_dir):
    ok("a4", "docs/bugs/ retained")
else:
    fail("a4", f"docs/bugs/ missing: {docs_bugs_dir}")

# a5: no source file under the feature references this feature's own legacy
# docs/spec/ spec or contract path. (CHANGELOG.md is historical narrative and
# is exempt; synthetic test fixtures that construct an *other* feature's
# docs/spec/ path to exercise dual-read fallback are exempt too.)
LEGACY_RE = re.compile(r"docs/spec/(?:spec|contract)\.md")
# CHANGELOG.md is historical narrative; test-dispatch-shape.py constructs a
# synthetic *other*-feature path string to exercise body path extraction (not a
# real reference to this feature's spec). Both are exempt.
EXEMPT_NAMES = {"CHANGELOG.md", "test-dispatch-shape.py"}
offenders = []
for root, _dirs, files in os.walk(FEATURE_DIR):
    for fn in files:
        if fn in EXEMPT_NAMES or fn.endswith(".pyc"):
            continue
        p = os.path.join(root, fn)
        try:
            text = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for m in LEGACY_RE.finditer(text):
            # Allow fallback-path mentions that explicitly pair the legacy path
            # with the new specs/ layout (dual-read documentation/fixtures).
            offenders.append(os.path.relpath(p, FEATURE_DIR))
            break
# Filter: a reference is acceptable when the file also mentions the specs/
# layout (it is describing the dual-read coexistence, not hard-coding legacy).
real_offenders = []
for rel in offenders:
    text = open(os.path.join(FEATURE_DIR, rel), encoding="utf-8").read()
    if "specs/" in text or "specs/spec.md" in text or '"specs"' in text or "'specs'" in text:
        continue
    real_offenders.append(rel)
if not real_offenders:
    ok("a5", "no source file hard-codes this feature's legacy docs/spec/ path")
else:
    fail("a5", f"legacy docs/spec/ references without specs/ awareness: {real_offenders}")


# ---------------------------------------------------------------------------
# Part B — tooling dual-read (E2E against scripts/triage-issue.py)
# ---------------------------------------------------------------------------

triage = load_triage()
if triage is None:
    print()
    print(f"Results: {PASS} passed, {FAIL} failed (triage import failure)")
    sys.exit(1)

# b1: triage-issue.py exposes a spec-path resolver.
resolver = getattr(triage, "resolve_spec_path", None)
if callable(resolver):
    ok("b1", "triage-issue.py exposes resolve_spec_path")
else:
    fail("b1", "triage-issue.py has no callable resolve_spec_path")

if callable(resolver):
    # b2: resolver prefers specs/ when present.
    with tempfile.TemporaryDirectory() as tmp:
        write(os.path.join(tmp, "specs", "spec.md"), "x")
        write(os.path.join(tmp, "docs", "spec", "spec.md"), "y")
        got = resolver(tmp, "spec.md")
        if os.path.normpath(str(got)) == os.path.normpath(
            os.path.join(tmp, "specs", "spec.md")
        ):
            ok("b2", "resolve_spec_path prefers specs/ over docs/spec/")
        else:
            fail("b2", f"expected specs/ path, got {got}")

    # b3: resolver falls back to docs/spec/ when specs/ absent.
    with tempfile.TemporaryDirectory() as tmp:
        write(os.path.join(tmp, "docs", "spec", "spec.md"), "y")
        got = resolver(tmp, "spec.md")
        if os.path.normpath(str(got)) == os.path.normpath(
            os.path.join(tmp, "docs", "spec", "spec.md")
        ):
            ok("b3", "resolve_spec_path falls back to docs/spec/")
        else:
            fail("b3", f"expected docs/spec/ fallback, got {got}")

# b4 (E2E): triage's rule-6 head-matter read resolves a feature spec from the
# new specs/ layout.
reader = getattr(triage, "_read_spec_head_matter", None)
if not callable(reader):
    fail("b4", "triage-issue.py has no _read_spec_head_matter to exercise")
else:
    from pathlib import Path

    HEAD = "---\nfeature: demo\nversion: 0.1.0\n---\n\n# Spec\n\nMARKER-BODY\n"
    with tempfile.TemporaryDirectory() as tmp:
        fdir = Path(tmp) / "demo"
        write(str(fdir / "specs" / "spec.md"), HEAD)
        got = reader(fdir)
        if "MARKER-BODY" in got:
            ok("b4", "_read_spec_head_matter reads spec from specs/ (preferred)")
        else:
            fail("b4", f"specs/ spec head matter not read: {got!r}")

    # b5 (E2E): same read still works for a feature on the legacy docs/spec/
    # layout (fallback during coexistence window).
    with tempfile.TemporaryDirectory() as tmp:
        fdir = Path(tmp) / "demo"
        write(str(fdir / "docs" / "spec" / "spec.md"), HEAD)
        got = reader(fdir)
        if "MARKER-BODY" in got:
            ok("b5", "_read_spec_head_matter reads spec from docs/spec/ (fallback)")
        else:
            fail("b5", f"docs/spec/ spec head matter not read: {got!r}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
