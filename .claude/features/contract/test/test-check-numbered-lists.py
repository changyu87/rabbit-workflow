#!/usr/bin/env python3
"""test-check-numbered-lists.py — Inv 33.

check-numbered-lists.py MUST exist, be executable, and reject Markdown files
whose ordered-list items or headings use decimal sub-numbers (1.1, 1.2.3) or
letter-suffixed numbering (1a, 3a)).

End-to-end fixtures: an invalid sample MUST exit 1; a valid sample MUST
exit 0.
"""

import os
import sys
import subprocess
import tempfile
import shutil

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-numbered-lists.py")

FAIL = 0

# t1: script exists and is executable
if not os.path.isfile(SCRIPT):
    print(f"FAIL t1: script not found at {SCRIPT}", file=sys.stderr)
    sys.exit(1)
if not os.access(SCRIPT, os.X_OK):
    print(f"FAIL t1: script not executable: {SCRIPT}", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: script exists and is executable")

# t2 (e2e): invalid sample with decimal heading -> exit 1
TMPDIR = tempfile.mkdtemp()
try:
    bad = os.path.join(TMPDIR, "bad-heading.md")
    with open(bad, "w") as f:
        f.write("# Title\n\n## 2.6 Subsection\n\nbody\n")
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t2: decimal heading not flagged (exit 0)", file=sys.stderr)
        print(f"  stdout: {proc.stdout}", file=sys.stderr)
        print(f"  stderr: {proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t2: decimal heading flagged (exit nonzero)")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t3 (e2e): invalid sample with letter-suffix heading -> exit 1
TMPDIR = tempfile.mkdtemp()
try:
    bad = os.path.join(TMPDIR, "bad-letter.md")
    with open(bad, "w") as f:
        f.write("# Title\n\n## 3a Subsection\n\nbody\n")
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t3: letter-suffix heading not flagged (exit 0)", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t3: letter-suffix heading flagged (exit nonzero)")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t4 (e2e): invalid sample with decimal list item -> exit 1
TMPDIR = tempfile.mkdtemp()
try:
    bad = os.path.join(TMPDIR, "bad-list.md")
    with open(bad, "w") as f:
        f.write("# Title\n\n1.2. nested item\n\n")
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t4: decimal list item not flagged (exit 0)", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t4: decimal list item flagged (exit nonzero)")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t5 (e2e): invalid sample with letter-suffix list item -> exit 1
TMPDIR = tempfile.mkdtemp()
try:
    bad = os.path.join(TMPDIR, "bad-list-letter.md")
    with open(bad, "w") as f:
        f.write("# Title\n\n3a) item\n\n")
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t5: letter-suffix list item not flagged (exit 0)", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t5: letter-suffix list item flagged (exit nonzero)")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t6 (e2e): valid sample with plain 1./2./3. -> exit 0
TMPDIR = tempfile.mkdtemp()
try:
    good = os.path.join(TMPDIR, "good.md")
    with open(good, "w") as f:
        f.write(
            "# Title\n\n## 2 Section\n\n"
            "1. first\n2. second\n3. third\n\n"
            "Some prose with a version like v1.2.3 and a regex (.*\\.py).\n"
        )
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(
            f"FAIL t6: valid sample flagged (exit {proc.returncode})",
            file=sys.stderr,
        )
        print(f"  stdout: {proc.stdout}", file=sys.stderr)
        print(f"  stderr: {proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t6: valid sample passes")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t7 (e2e smoke): run script against the real in-scope set; must pass.
# This guards against drift sneaking into the spec/SKILL/agent docs.
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
import glob

targets = []
targets.extend(
    glob.glob(
        os.path.join(REPO_ROOT, ".claude/features/*/docs/spec/*.md")
    )
)
targets.extend(
    glob.glob(
        os.path.join(REPO_ROOT, ".claude/features/**/skills/**/SKILL.md"),
        recursive=True,
    )
)
targets.extend(
    glob.glob(
        os.path.join(REPO_ROOT, ".claude/features/**/agents/**/*.md"),
        recursive=True,
    )
)
targets.extend(glob.glob(os.path.join(REPO_ROOT, ".claude/features/policy/*.md")))
targets.extend(
    glob.glob(
        os.path.join(REPO_ROOT, ".claude/features/contract/docs/**/*.md"),
        recursive=True,
    )
)
for name in ("CLAUDE.md", "README.md"):
    p = os.path.join(REPO_ROOT, name)
    if os.path.exists(p):
        targets.append(p)

# de-dup and only existing files
targets = sorted({os.path.realpath(p) for p in targets if os.path.exists(p)})

if not targets:
    print("FAIL t7: no in-scope .md files found", file=sys.stderr)
    FAIL = 1
else:
    proc = subprocess.run(
        ["python3", SCRIPT, *targets], capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(
            f"FAIL t7: real-files smoke check found violations (exit {proc.returncode})",
            file=sys.stderr,
        )
        print(f"  stdout: {proc.stdout}", file=sys.stderr)
        print(f"  stderr: {proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        print(f"PASS t7: {len(targets)} real .md files pass")

if FAIL:
    print("test-check-numbered-lists: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-numbered-lists: all checks passed.")
