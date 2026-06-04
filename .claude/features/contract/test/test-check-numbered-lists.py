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

# t8 (e2e): prose-embedded fractional numbering -> exit 1.
# A numbering keyword (phase/step/item/part/section, singular or plural)
# immediately followed by an N.M index in running prose is a violation
# (Inv 33), even when it does not start a list item or heading.
TMPDIR = tempfile.mkdtemp()
try:
    bad = os.path.join(TMPDIR, "prose-decimal.md")
    with open(bad, "w") as f:
        f.write("# Title\n\nDuring phase 1.5 the loop performs the merge.\n")
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t8: prose 'phase 1.5' not flagged (exit 0)", file=sys.stderr)
        FAIL = 1
    elif "prose-decimal" not in proc.stderr:
        print(
            "FAIL t8: prose decimal flagged but not under 'prose-decimal' label",
            file=sys.stderr,
        )
        print(f"  stderr: {proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t8: prose 'phase 1.5' flagged as prose-decimal")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t9 (e2e): prose-embedded letter-suffixed numbering -> exit 1.
# Covers both the 'step 2.b' (N.a) and 'item 3a' (Na) spellings.
TMPDIR = tempfile.mkdtemp()
try:
    bad = os.path.join(TMPDIR, "prose-letter.md")
    with open(bad, "w") as f:
        f.write("# Title\n\nSee step 2.b and then item 3a for the rest.\n")
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t9: prose 'step 2.b'/'item 3a' not flagged (exit 0)", file=sys.stderr)
        FAIL = 1
    elif "prose-letter" not in proc.stderr:
        print(
            "FAIL t9: prose letter flagged but not under 'prose-letter' label",
            file=sys.stderr,
        )
        print(f"  stderr: {proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t9: prose 'step 2.b'/'item 3a' flagged as prose-letter")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t10 (e2e): legitimate decimal literals MUST NOT be flagged -> exit 0.
# The prose patterns are anchored to a numbering keyword and require the
# index to IMMEDIATELY follow it, so version strings, schema_version values,
# invariant references, dotted filenames, currency, and a number that does
# not directly follow the keyword ('phase completed in 1.5 seconds') all
# pass. Documentation examples written inside `inline code spans` (e.g. the
# spec's own `phase 1.5` example) also pass — a numbered index inside
# backticks is a literal reference, not running prose.
TMPDIR = tempfile.mkdtemp()
try:
    good = os.path.join(TMPDIR, "decimals-ok.md")
    with open(good, "w") as f:
        f.write(
            "# Title\n\n"
            "Upgrade to release/1.12.0 or v1.5.0 soon.\n"
            "The schema_version 2.16.0 is current.\n"
            "See Inv 33 for the rule and foo.1.5.bar for the file.\n"
            "The total cost is $5.50 per unit.\n"
            "The phase completed in 1.5 seconds last run.\n"
            "Documentation example: `phase 1.5` and `step 2.b` are flagged.\n"
        )
    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR], capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(
            f"FAIL t10: legitimate decimals flagged (exit {proc.returncode})",
            file=sys.stderr,
        )
        print(f"  stdout: {proc.stdout}", file=sys.stderr)
        print(f"  stderr: {proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t10: legitimate decimal literals pass")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t11 (e2e smoke): run script against the real in-scope set; must pass.
# This guards against drift sneaking into the spec/SKILL/agent docs.
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
import glob

targets = []
# A feature's spec/contract docs live under EITHER the flat docs/ layout
# (preferred) or the specs/ layout (fallback) per the dual-read resolver in
# lib/checks.py (Inv 68). Globbing only specs/*.md would silently exclude
# every feature migrated to the flat docs/ layout from this scan — a false
# green (Inv 69 class). Glob both layouts, but ONLY the spec/contract doc
# surfaces named in Inv 33's in-scope set (spec.md, contract.md) — NEVER
# CHANGELOG.md. The CHANGELOG is the documented home for historical
# phase/step labels (Inv 39) and is exempt from doc-hygiene scans by
# construction (Inv 49: "CHANGELOG.md is never scanned"); sweeping it in
# would flag legitimate historical 'Phase 2b'-style tombstone prose.
for layout in ("specs", "docs"):
    for leaf in ("spec.md", "contract.md"):
        targets.extend(
            glob.glob(
                os.path.join(REPO_ROOT, ".claude/features/*", layout, leaf)
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
# contract's own spec/contract surfaces (already covered by the per-feature
# spec.md/contract.md glob above for the docs/ layout, but kept explicit here
# to mirror Inv 33's "contract/specs/**/*.md" in-scope clause). CHANGELOG.md
# is deliberately excluded (Inv 39/Inv 49 — historical phase labels live
# there and are exempt from doc-hygiene scans).
for leaf in ("spec.md", "contract.md"):
    targets.extend(
        glob.glob(os.path.join(REPO_ROOT, ".claude/features/contract/docs", leaf))
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
