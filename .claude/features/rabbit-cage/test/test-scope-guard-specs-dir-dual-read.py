#!/usr/bin/env python3
"""E2E: scope-guard.py spec.md path-pattern carve-out is dual-read across
the docs/spec/ -> specs/ migration (issue #399 Phase 2, rabbit-cage).

The spec.md carve-out (Inv 5 standalone, Inv 17(a2) plugin) MUST ALLOW
unconditional writes to a feature's spec.md under BOTH the new layout
(<feature>/specs/spec.md) AND the legacy layout (<feature>/docs/spec/spec.md)
during the coexistence window, in both standalone and plugin modes. This
mirrors contract's resolve_spec_path dual-read (Phase 1, #451) so a
mid-migration feature still matches the carve-out regardless of which layout
it currently uses.

The carve-out stays NARROW: only the literal basename spec.md under either
specs/ or docs/spec/ is allowed without a scope marker; other writes in the
feature dir still flow through the marker gate.
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

STANDALONE_FEATURE = "specs-dual-standalone-test"
PLUGIN_FEATURE = "specs-dual-plugin-test"

# Standalone-mode targets (.claude/features/<name>/...)
SA_SPECS = os.path.join(
    REPO_ROOT, ".claude/features", STANDALONE_FEATURE, "specs", "spec.md"
)
SA_DOCS = os.path.join(
    REPO_ROOT, ".claude/features", STANDALONE_FEATURE, "docs", "spec", "spec.md"
)
# A non-spec.md write under specs/ must still be DENIED (carve-out is narrow).
SA_SPECS_CONTRACT = os.path.join(
    REPO_ROOT, ".claude/features", STANDALONE_FEATURE, "specs", "contract.md"
)

# Plugin-mode targets (.rabbit/rabbit-project/features/<name>/...)
PL_SPECS = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit-project", "features",
    PLUGIN_FEATURE, "specs", "spec.md",
)
PL_DOCS = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit-project", "features",
    PLUGIN_FEATURE, "docs", "spec", "spec.md",
)
PL_SPECS_CONTRACT = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit-project", "features",
    PLUGIN_FEATURE, "specs", "contract.md",
)


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
    print("test-scope-guard-specs-dir-dual-read.py")
    print()
    with saved_state():
        # Standalone mode: no .rabbit/.runtime/mode file.
        expect_allow("standalone specs/spec.md", SA_SPECS)
        expect_allow("standalone docs/spec/spec.md (legacy)", SA_DOCS)
        expect_deny("standalone specs/contract.md (non-spec.md)",
                    SA_SPECS_CONTRACT)

        # Plugin mode.
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("plugin")
        expect_allow("plugin specs/spec.md", PL_SPECS)
        expect_allow("plugin docs/spec/spec.md (legacy)", PL_DOCS)
        expect_deny("plugin specs/contract.md (non-spec.md)",
                    PL_SPECS_CONTRACT)

    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(main())
