#!/usr/bin/env python3
"""Asserts rabbit-cage source files contain no .rbt- references."""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def grep_lines(path, needle):
    try:
        with open(path) as f:
            lines = []
            for i, line in enumerate(f, 1):
                if needle in line:
                    lines.append(f"{i}:{line.rstrip()}")
            return lines
    except Exception:
        return []


print("test-no-rbt-refs.py")
print()

# t1: feature session-init
print("=== t1: .claude/features/rabbit-cage/hooks/session-init.py has no .rbt- refs ===")
si = os.path.join(FEATURE_DIR, "hooks/session-init.py")
matches = grep_lines(si, ".rbt-")
if matches:
    fail_t("session-init.py (feature) still contains .rbt- references:\n" + "\n".join(matches[:5]))
else:
    ok("session-init.py (feature) has no .rbt- references")

# t2: deployed
print("=== t2: .claude/hooks/session-init.py has no .rbt- refs ===")
sid = os.path.join(REPO_ROOT, ".claude/hooks/session-init.py")
if os.path.islink(sid):
    sid_real = os.path.realpath(sid)
else:
    sid_real = sid
matches = grep_lines(sid_real, ".rbt-")
if matches:
    fail_t("session-init.py (deployed) still contains .rbt- references:\n" + "\n".join(matches[:5]))
else:
    ok("session-init.py (deployed) has no .rbt- references")

# t3: spec.md
print("=== t3: spec.md has no .rbt- refs ===")
spec = os.path.join(FEATURE_DIR, "docs/spec/spec.md")
matches = grep_lines(spec, ".rbt-")
if matches:
    fail_t("spec.md still contains .rbt- references:\n" + "\n".join(matches[:5]))
else:
    ok("spec.md has no .rbt- references")

# t4: contract.md
print("=== t4: contract.md has no .rbt- refs ===")
contract = os.path.join(FEATURE_DIR, "docs/spec/contract.md")
matches = grep_lines(contract, ".rbt-")
if matches:
    fail_t("contract.md still contains .rbt- references:\n" + "\n".join(matches[:5]))
else:
    ok("contract.md has no .rbt- references")

# t5: all source dirs
print("=== t5: all rabbit-cage source (non-test) files have no .rbt- refs ===")
found_files = []
source_dirs = [
    os.path.join(FEATURE_DIR, "hooks"),
    os.path.join(FEATURE_DIR, "scripts"),
    os.path.join(FEATURE_DIR, "commands"),
    os.path.join(FEATURE_DIR, "docs"),
]
for d in source_dirs:
    if not os.path.isdir(d):
        continue
    for root, _, files in os.walk(d):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath) as f:
                    if ".rbt-" in f.read():
                        found_files.append(fpath)
            except Exception:
                pass

for jf in (os.path.join(FEATURE_DIR, "feature.json"), os.path.join(FEATURE_DIR, "settings.json")):
    if not os.path.isfile(jf):
        continue
    try:
        with open(jf) as f:
            if ".rbt-" in f.read():
                found_files.append(jf)
    except Exception:
        pass

if not found_files:
    ok("no rabbit-cage source files contain .rbt- references")
else:
    msg = "the following rabbit-cage source files still contain .rbt- references:"
    for f in found_files:
        msg += f"\n    {f}:"
        for line in grep_lines(f, ".rbt-")[:3]:
            msg += f"\n      {line}"
    fail_t(msg)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
