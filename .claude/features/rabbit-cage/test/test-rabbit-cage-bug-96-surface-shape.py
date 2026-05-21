#!/usr/bin/env python3
"""test-rabbit-cage-bug-96-surface-shape.py — surface-path reality check.

RABBIT-CAGE-BUG-96: spec invariants 1, 2, 4, 5, 6, 7 previously claimed
several surface paths were symlinks; filesystem reality was copy-file
deployment (or non-existent paths). This test locks the spec-vs-reality
correspondence so the drift cannot resurface.

For each surface path the spec describes, assert:
  - Files claimed as "real file" (copy-file deployment) are regular files
    (not symlinks).
  - Directories claimed as "real directory" (copy-file population) are
    real directories (not symlinks).
  - Paths claimed as "does not exist" actually don't exist.

If anyone re-introduces a symlink-flavored spec claim without changing
the build, OR converts a copy-file target to a symlink without updating
the spec, this test fails.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when build-contract.json is replaced by a
    different deployment mechanism for rabbit-cage's surface.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


# Inv 1: .claude/commands is a real directory, NOT a symlink
p = os.path.join(REPO_ROOT, ".claude", "commands")
if os.path.islink(p):
    ko(f"Inv 1: .claude/commands is a symlink (spec says real directory): {p}")
elif os.path.isdir(p):
    ok("Inv 1: .claude/commands is a real directory (not symlink)")
else:
    ko(f"Inv 1: .claude/commands missing or not a directory: {p}")

# Inv 2: .claude/hooks is a real directory, NOT a symlink
p = os.path.join(REPO_ROOT, ".claude", "hooks")
if os.path.islink(p):
    ko(f"Inv 2: .claude/hooks is a symlink (spec says real directory): {p}")
elif os.path.isdir(p):
    ok("Inv 2: .claude/hooks is a real directory (not symlink)")
else:
    ko(f"Inv 2: .claude/hooks missing or not a directory: {p}")

# Inv 3: .claude/skills is a real directory (already covered by test-generated-surface.py)

# Inv 4: .claude/settings.json is a real file, NOT a symlink
p = os.path.join(REPO_ROOT, ".claude", "settings.json")
if os.path.islink(p):
    ko(f"Inv 4: .claude/settings.json is a symlink (spec says real file): {p}")
elif os.path.isfile(p):
    ok("Inv 4: .claude/settings.json is a real file (not symlink)")
else:
    ko(f"Inv 4: .claude/settings.json missing or not a file: {p}")

# Inv 5: .claude/policy/ MUST NOT exist (consumers use .claude/features/policy/ directly)
p = os.path.join(REPO_ROOT, ".claude", "policy")
if os.path.exists(p) or os.path.islink(p):
    ko(f"Inv 5: .claude/policy/ exists (spec says no indirection path): {p}")
else:
    ok("Inv 5: .claude/policy/ does not exist (consumers use .claude/features/policy/ directly)")

# Inv 6: .claude/contract/ MUST NOT exist (consumers use .claude/features/contract/ directly)
p = os.path.join(REPO_ROOT, ".claude", "contract")
if os.path.exists(p) or os.path.islink(p):
    ko(f"Inv 6: .claude/contract/ exists (spec says no indirection path): {p}")
else:
    ok("Inv 6: .claude/contract/ does not exist (consumers use .claude/features/contract/ directly)")

# Inv 7: README.md at repo root is a real file, NOT a symlink
p = os.path.join(REPO_ROOT, "README.md")
if os.path.islink(p):
    ko(f"Inv 7: README.md is a symlink (spec says real file): {p}")
elif os.path.isfile(p):
    ok("Inv 7: README.md is a real file (not symlink)")
else:
    ko(f"Inv 7: README.md missing or not a file: {p}")

# Inv 8: install.py at repo root is a real file (already says "copy", not "symlink", in spec)
p = os.path.join(REPO_ROOT, "install.py")
if os.path.islink(p):
    ko(f"Inv 8: install.py is a symlink (spec says copy-file): {p}")
elif os.path.isfile(p):
    ok("Inv 8: install.py is a real file (not symlink)")
else:
    ko(f"Inv 8: install.py missing or not a file: {p}")

# Inv 9: CLAUDE.md @-imports MUST source from .claude/features/policy/, NOT .claude/policy/
claude_md = os.path.join(REPO_ROOT, "CLAUDE.md")
with open(claude_md) as f:
    claude_text = f.read()
bad_path = "@.claude/policy/"
good_path = "@.claude/features/policy/"
if bad_path in claude_text:
    ko(f"Inv 9: CLAUDE.md uses legacy {bad_path!r} @-import (spec says {good_path!r}): {claude_md}")
elif good_path in claude_text:
    ok(f"Inv 9: CLAUDE.md @-imports source from {good_path!r}")
else:
    ko(f"Inv 9: CLAUDE.md has no recognizable policy @-imports at {good_path!r}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{FAIL} TEST(S) FAILED")
    sys.exit(1)
