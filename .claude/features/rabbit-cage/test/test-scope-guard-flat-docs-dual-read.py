#!/usr/bin/env python3
"""E2E: scope-guard.py spec-artifact path-pattern carve-out recognizes the
FLAT docs/ layout (rabbit-cage).

The per-feature documentation home is migrating to a flat docs/ directory:
  specs/spec.md      -> docs/spec.md
  specs/contract.md  -> docs/contract.md
  <feature>/CHANGELOG.md -> docs/CHANGELOG.md

During the coexistence window the spec-artifact carve-out (Inv 5 standalone,
Inv 17(a2) plugin) MUST ALLOW unconditional writes to a feature's
docs/spec.md, docs/contract.md, and docs/CHANGELOG.md (the flat layout) so
the per-feature Phase 2 move is permitted, IN ADDITION to the existing
layouts: specs/spec.md (current) and docs/spec/spec.md (older nested). This
applies in both standalone and plugin modes.

The carve-out stays NARROW:
  - under FLAT docs/, only the three literal basenames spec.md / contract.md /
    CHANGELOG.md are allowed without a marker; an arbitrary docs/<other>.md
    write still flows through the marker gate.
  - under specs/, only spec.md is allowed (specs/contract.md still DENIED,
    unchanged) — the flat-docs broadening does NOT widen the specs/ form.
"""
import contextlib
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py"
)

RUNTIME_DIR = os.path.join(REPO_ROOT, ".rabbit", ".runtime")
MODE_FILE = os.path.join(RUNTIME_DIR, "mode")

STANDALONE_FEATURE = "flat-docs-dual-standalone-test"
PLUGIN_FEATURE = "flat-docs-dual-plugin-test"


def _sa(*parts):
    return os.path.join(
        REPO_ROOT, ".claude/features", STANDALONE_FEATURE, *parts
    )


def _pl(*parts):
    return os.path.join(
        REPO_ROOT, ".rabbit", "rabbit-project", "features",
        PLUGIN_FEATURE, *parts,
    )


# Standalone-mode flat-docs targets (the NEW layout — must ALLOW).
SA_DOCS_SPEC = _sa("docs", "spec.md")
SA_DOCS_CONTRACT = _sa("docs", "contract.md")
SA_DOCS_CHANGELOG = _sa("docs", "CHANGELOG.md")
# Existing layouts (fallback preserved — must still ALLOW).
SA_SPECS_SPEC = _sa("specs", "spec.md")
SA_DOCS_SPEC_NESTED = _sa("docs", "spec", "spec.md")
# Narrow carve-out: an arbitrary docs/<other>.md still DENIED.
SA_DOCS_OTHER = _sa("docs", "random.md")
# specs/contract.md still DENIED (flat broadening does not widen specs/).
SA_SPECS_CONTRACT = _sa("specs", "contract.md")

# Plugin-mode flat-docs targets.
PL_DOCS_SPEC = _pl("docs", "spec.md")
PL_DOCS_CONTRACT = _pl("docs", "contract.md")
PL_DOCS_CHANGELOG = _pl("docs", "CHANGELOG.md")
PL_SPECS_SPEC = _pl("specs", "spec.md")
PL_DOCS_SPEC_NESTED = _pl("docs", "spec", "spec.md")
PL_DOCS_OTHER = _pl("docs", "random.md")
PL_SPECS_CONTRACT = _pl("specs", "contract.md")


@contextlib.contextmanager
def saved_state():
    paths = [MODE_FILE]
    saved = {}
    for p in paths:
        if os.path.isfile(p):
            with open(p, "rb") as f:
                saved[p] = f.read()
            os.remove(p)
    try:
        yield
    finally:
        for p in paths:
            if os.path.isfile(p):
                os.remove(p)
        for p, content in saved.items():
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(content)


def run_guard(target_path):
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": target_path, "content": "x"}}
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return result.returncode, result.stderr


pass_n = 0
fail_n = 0


def expect_allow(label, target):
    global pass_n, fail_n
    rc, stderr = run_guard(target)
    if rc == 0:
        print(f"  PASS: {label} ALLOWED")
        pass_n += 1
    else:
        print(f"  FAIL: {label} expected ALLOW (rc=0), got rc={rc} "
              f"stderr={stderr!r}")
        fail_n += 1


def expect_deny(label, target):
    global pass_n, fail_n
    rc, _ = run_guard(target)
    if rc != 0:
        print(f"  PASS: {label} DENIED (narrow carve-out preserved)")
        pass_n += 1
    else:
        print(f"  FAIL: {label} expected DENY (rc!=0), got rc=0")
        fail_n += 1


def main():
    print("test-scope-guard-flat-docs-dual-read.py")
    print()
    with saved_state():
        # Standalone mode: no .rabbit/.runtime/mode file.
        expect_allow("standalone docs/spec.md (flat)", SA_DOCS_SPEC)
        expect_allow("standalone docs/contract.md (flat)", SA_DOCS_CONTRACT)
        expect_allow("standalone docs/CHANGELOG.md (flat)", SA_DOCS_CHANGELOG)
        expect_allow("standalone specs/spec.md (current)", SA_SPECS_SPEC)
        expect_allow("standalone docs/spec/spec.md (legacy nested)",
                     SA_DOCS_SPEC_NESTED)
        expect_deny("standalone docs/random.md (non-artifact)", SA_DOCS_OTHER)
        expect_deny("standalone specs/contract.md (specs/ unchanged)",
                    SA_SPECS_CONTRACT)

        # Plugin mode.
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("plugin")
        expect_allow("plugin docs/spec.md (flat)", PL_DOCS_SPEC)
        expect_allow("plugin docs/contract.md (flat)", PL_DOCS_CONTRACT)
        expect_allow("plugin docs/CHANGELOG.md (flat)", PL_DOCS_CHANGELOG)
        expect_allow("plugin specs/spec.md (current)", PL_SPECS_SPEC)
        expect_allow("plugin docs/spec/spec.md (legacy nested)",
                     PL_DOCS_SPEC_NESTED)
        expect_deny("plugin docs/random.md (non-artifact)", PL_DOCS_OTHER)
        expect_deny("plugin specs/contract.md (specs/ unchanged)",
                    PL_SPECS_CONTRACT)

    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(main())
