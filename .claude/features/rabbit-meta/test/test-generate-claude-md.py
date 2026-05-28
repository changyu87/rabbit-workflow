#!/usr/bin/env python3
"""test-generate-claude-md.py — Inv 2

End-to-end test verifying CLAUDE.md template + generate_claude_md generator:
  - t1: template file exists at expected location
  - t2: template contains the killer-story prose ("rabbit-feature-new")
  - t3: template contains all three @-imports of policy files
  - t4: each @-imported policy file actually exists on disk
  - t5: generator writes the output verbatim
  - t6: generator is idempotent (second call returns "no-op")
  - t7: generator raises FileNotFoundError on missing template
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.generate_claude_md import generate_claude_md  # noqa: E402

TEMPLATE_PATH = os.path.join(FEATURE_DIR, "templates", "CLAUDE.md.template")

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS {n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL {n}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: template file exists
if os.path.isfile(TEMPLATE_PATH):
    ok("t1", f"template exists at {TEMPLATE_PATH}")
else:
    fail_t("t1", f"template missing at {TEMPLATE_PATH}")

# Load template content for subsequent tests; bail gracefully if missing.
template_content = ""
if os.path.isfile(TEMPLATE_PATH):
    with open(TEMPLATE_PATH, "r") as f:
        template_content = f.read()

# t2: killer-story prose
if "rabbit-feature-new" in template_content:
    ok("t2", "template contains killer-story ('rabbit-feature-new')")
else:
    fail_t("t2", "template missing killer-story marker 'rabbit-feature-new'")

# t3: three @-imports of policy files
policy_imports = [
    "@.claude/features/policy/philosophy.md",
    "@.claude/features/policy/spec-rules.md",
    "@.claude/features/policy/coding-rules.md",
]
missing_imports = [imp for imp in policy_imports if imp not in template_content]
if not missing_imports:
    ok("t3", "template contains all three @-imports")
else:
    fail_t("t3", f"template missing @-imports: {missing_imports}")

# t4: each @-imported policy file exists on disk (resolve relative to repo root)
missing_policy = []
for imp in policy_imports:
    rel = imp.lstrip("@")
    abs_path = os.path.join(REPO_ROOT, rel)
    if not os.path.isfile(abs_path):
        missing_policy.append(abs_path)
if not missing_policy:
    ok("t4", "all three @-imported policy files exist on disk")
else:
    fail_t("t4", f"missing policy files: {missing_policy}")

# t5: generator writes the output verbatim
with tempfile.TemporaryDirectory() as tmp:
    out_path = os.path.join(tmp, "CLAUDE.md")
    result = generate_claude_md(TEMPLATE_PATH, out_path)
    if result != "wrote":
        fail_t("t5", f"expected return 'wrote', got {result!r}")
    else:
        with open(out_path, "r") as f:
            written = f.read()
        if written == template_content:
            ok("t5", "generator wrote output verbatim")
        else:
            fail_t("t5", "written content does not match template verbatim")

# t6: idempotent — second call returns "no-op"
with tempfile.TemporaryDirectory() as tmp:
    out_path = os.path.join(tmp, "CLAUDE.md")
    r1 = generate_claude_md(TEMPLATE_PATH, out_path)
    r2 = generate_claude_md(TEMPLATE_PATH, out_path)
    if r1 == "wrote" and r2 == "no-op":
        ok("t6", "generator is idempotent (wrote then no-op)")
    else:
        fail_t("t6", f"expected ('wrote', 'no-op'), got ({r1!r}, {r2!r})")

# t7: FileNotFoundError on missing template
with tempfile.TemporaryDirectory() as tmp:
    missing = os.path.join(tmp, "does-not-exist.template")
    out_path = os.path.join(tmp, "CLAUDE.md")
    try:
        generate_claude_md(missing, out_path)
        fail_t("t7", "expected FileNotFoundError, no exception raised")
    except FileNotFoundError:
        ok("t7", "raised FileNotFoundError on missing template")
    except Exception as e:
        fail_t("t7", f"expected FileNotFoundError, got {type(e).__name__}: {e}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
