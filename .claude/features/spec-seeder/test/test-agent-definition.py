#!/usr/bin/env python3
"""test-agent-definition.py — spec-seeder Inv 1: agent definition shape."""

import os
import sys

AGENT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "agents", "spec-seeder.md",
))

PASS = 0
FAIL = 0


def ok(n, m):
    global PASS
    print(f"  PASS {n}: {m}")
    PASS += 1


def fail_t(n, m):
    global FAIL
    print(f"  FAIL {n}: {m}", file=sys.stderr)
    FAIL += 1


def parse_frontmatter(content):
    if not content.startswith("---\n"):
        return None
    end = content.find("\n---\n", 4)
    if end < 0:
        return None
    fm = {}
    for line in content[4:end].split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


# t1: file exists
if os.path.isfile(AGENT):
    ok("t1", f"{AGENT} exists")
else:
    fail_t("t1", f"missing: {AGENT}")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)

with open(AGENT) as f:
    content = f.read()

fm = parse_frontmatter(content)
if fm is None:
    fail_t("t-frontmatter", "could not parse YAML frontmatter")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)

# t2: name field
if fm.get("name") == "spec-seeder":
    ok("t2", "name == spec-seeder")
else:
    fail_t("t2", f"name == {fm.get('name')!r} (expected 'spec-seeder')")

# t3: tools field (exact — read-only enforcement)
if fm.get("tools") == "Read, Grep, Glob":
    ok("t3", "tools field is exactly 'Read, Grep, Glob' (read-only enforced)")
else:
    fail_t("t3", f"tools == {fm.get('tools')!r} (expected exactly 'Read, Grep, Glob')")

# t4: description present
if fm.get("description"):
    ok("t4", "description present")
else:
    fail_t("t4", "description missing or empty")

# t5: ownership metadata
for key in ("version", "owner", "deprecation_criterion"):
    if fm.get(key):
        ok(f"t5[{key}]", f"{key} present")
    else:
        fail_t(f"t5[{key}]", f"{key} missing")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
