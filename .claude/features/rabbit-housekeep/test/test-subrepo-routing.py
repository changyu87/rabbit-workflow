#!/usr/bin/env python3
"""test-subrepo-routing.py — assert that wave sub-issue filing targets the
consuming project's GitHub remote, not the framework's hardwired repo (issue #1206).

When a housekeep wave flags a gap and files a housekeeping-tagged sub-issue via
file-item.py, the target repo must be the CONSUMING PROJECT's GitHub remote, not
changyu87/rabbit-workflow. The mechanism is the RABBIT_ISSUE_REPO env var that
_gh.py's repo_slug() honours.

Asserts, against the real feature tree:

  r0: scripts/resolve-project-remote.py exists.
  r1: resolve-project-remote.py resolves a git-remote-origin URL to an
      owner/repo slug: git@github.com:owner/repo.git -> owner/repo,
      https://github.com/owner/repo.git -> owner/repo,
      https://github.com/owner/repo    -> owner/repo.
  r2: resolve-project-remote.py exits 1 when the directory is not a git repo
      (no remote discoverable), printing nothing or only an error to stderr.
  r3: The SKILL.md documents that wave sub-issues are filed into the
      CONSUMING PROJECT's repo (not the framework's repo), and that
      RABBIT_ISSUE_REPO is set from the consuming project's remote.
  r4: feature.json surface.scripts lists resolve-project-remote.py so the
      script is a declared artifact.

Non-interactive. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "resolve-project-remote.py")
SKILL_MD = os.path.join(FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md")
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

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


# r0: script exists
if not os.path.isfile(SCRIPT):
    fail("r0", f"missing: {SCRIPT}")
else:
    ok("r0", "scripts/resolve-project-remote.py exists")

# r1: resolves remote URLs to owner/repo slug
if os.path.isfile(SCRIPT):
    cases = [
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo", "owner/repo"),
        ("git@github.com:acme-org/my-project.git", "acme-org/my-project"),
    ]
    r1_ok = True
    for url, expected in cases:
        r = subprocess.run(
            ["python3", SCRIPT, "--url", url],
            capture_output=True, text=True,
        )
        got = r.stdout.strip()
        if r.returncode != 0 or got != expected:
            fail("r1", f"--url {url!r}: expected {expected!r}, got {got!r} "
                       f"(rc={r.returncode}, stderr={r.stderr.strip()})")
            r1_ok = False
            break
    if r1_ok:
        ok("r1", f"resolves {len(cases)} URL forms to owner/repo slug correctly")

# r2: non-git directory exits non-zero
if os.path.isfile(SCRIPT):
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            ["python3", SCRIPT, "--root", tmp],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            ok("r2", f"non-git dir exits non-zero (rc={r.returncode})")
        else:
            fail("r2", f"non-git dir must exit non-zero; stdout={r.stdout.strip()!r}")

# r3: SKILL.md documents consuming-project repo routing for sub-issue filing
if os.path.isfile(SKILL_MD):
    with open(SKILL_MD, encoding="utf-8") as f:
        skill_text = f.read()
    # Must mention that RABBIT_ISSUE_REPO is set from the consuming project remote
    mentions_rabbit_issue_repo = "RABBIT_ISSUE_REPO" in skill_text
    # Must reference the new script
    mentions_resolve_remote = "resolve-project-remote.py" in skill_text
    if mentions_rabbit_issue_repo and mentions_resolve_remote:
        ok("r3", "SKILL.md documents RABBIT_ISSUE_REPO routing via "
                 "resolve-project-remote.py")
    else:
        fail("r3", "SKILL.md must document that wave sub-issues route to the "
                   "consuming project's repo via RABBIT_ISSUE_REPO set from "
                   "resolve-project-remote.py "
                   f"(RABBIT_ISSUE_REPO={mentions_rabbit_issue_repo}, "
                   f"resolve-project-remote={mentions_resolve_remote})")
else:
    fail("r3", f"missing: {SKILL_MD}")

# r4: feature.json surface.scripts lists the new script
with open(FEATURE_JSON, encoding="utf-8") as f:
    fjson = json.load(f)
surface_scripts = fjson.get("surface", {}).get("scripts", []) or []
# The declared path uses the relative form consistent with the existing entries
expected_entry = "scripts/resolve-project-remote.py"
if expected_entry in surface_scripts:
    ok("r4", f"feature.json surface.scripts declares {expected_entry}")
else:
    fail("r4", f"feature.json surface.scripts must include {expected_entry!r}; "
               f"got {surface_scripts}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
