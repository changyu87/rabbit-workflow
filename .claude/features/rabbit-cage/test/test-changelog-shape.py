#!/usr/bin/env python3
"""rabbit-cage e2e — CHANGELOG.md shape enforcement (spec Inv 30).

Pins the four shape assertions described in rabbit-cage spec.md Inv 30:
  (i)   CHANGELOG.md exists at repo root.
  (ii)  The top-most non-intro `## [` header is `## [Unreleased]`.
  (iii) Every `## [release/X.Y]` header matches the
        `## [release/X.Y] - YYYY-MM-DD` shape (regex).
  (iv)  For every release branch `release/X.Y` that exists in `git branch -r`,
        a `## [release/X.Y]` header is present in CHANGELOG.md. When the git
        remote is unreachable the test reports the skip and proceeds.

Bug #292 — initial seed.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CHANGELOG = os.path.join(REPO_ROOT, "CHANGELOG.md")

RELEASE_HEADER_RE = re.compile(
    r"^## \[release/[0-9]+\.[0-9]+\] - \d{4}-\d{2}-\d{2}\s*$"
)
RELEASE_NAME_IN_HEADER_RE = re.compile(r"^## \[(release/[0-9]+\.[0-9]+)\]")
ANY_RELEASE_LINE_RE = re.compile(r"^## \[release/[0-9]+\.[0-9]+\]")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-changelog-shape.py")

# t1 — CHANGELOG.md exists at repo root.
if os.path.isfile(CHANGELOG):
    ok(1, f"CHANGELOG.md present at {CHANGELOG}")
else:
    fail_t(1, f"CHANGELOG.md missing at {CHANGELOG}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

with open(CHANGELOG) as fh:
    body = fh.read()
lines = body.splitlines()

# t2 — top-most `## [` header is `## [Unreleased]`.
top_header = None
for ln in lines:
    if ln.startswith("## ["):
        top_header = ln.rstrip()
        break
if top_header is None:
    fail_t(2, "no `## [` header found in CHANGELOG.md")
elif top_header == "## [Unreleased]":
    ok(2, "first `## [` header is `## [Unreleased]`")
else:
    fail_t(2, f"first `## [` header is {top_header!r}, expected `## [Unreleased]`")

# t3 — every `## [release/X.Y]` header matches the dated-release shape.
shape_violations = []
release_headers_in_doc = []
for ln in lines:
    if ANY_RELEASE_LINE_RE.match(ln):
        m = RELEASE_NAME_IN_HEADER_RE.match(ln)
        if m:
            release_headers_in_doc.append(m.group(1))
        if not RELEASE_HEADER_RE.match(ln.rstrip()):
            shape_violations.append(ln.rstrip())
if shape_violations:
    fail_t(3, f"release headers violating shape: {shape_violations}")
else:
    ok(3, f"all {len(release_headers_in_doc)} release headers match `## [release/X.Y] - YYYY-MM-DD`")

# t4 — every `release/X.Y` remote branch is represented as a header.
git_proc = subprocess.run(
    ["git", "-C", REPO_ROOT, "branch", "-r"],
    capture_output=True, text=True,
)
if git_proc.returncode != 0:
    ok(4, f"`git branch -r` unavailable (rc={git_proc.returncode}); skipping per-branch check")
else:
    remote_releases = []
    for ln in git_proc.stdout.splitlines():
        token = ln.strip().split()[0] if ln.strip() else ""
        # Match origin/release/X.Y  (or any-remote/release/X.Y)
        m = re.match(r"^[^/]+/(release/[0-9]+\.[0-9]+)$", token)
        if m:
            remote_releases.append(m.group(1))
    if not remote_releases:
        ok(4, "no `release/X.Y` remote branches found; skipping per-branch check")
    else:
        missing = [r for r in remote_releases if r not in release_headers_in_doc]
        if missing:
            fail_t(4, f"remote release branches missing from CHANGELOG.md: {sorted(set(missing))}")
        else:
            ok(4, f"all {len(set(remote_releases))} remote release branches represented in CHANGELOG.md")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
