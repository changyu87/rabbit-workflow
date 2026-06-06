#!/usr/bin/env python3
"""test-decomposition-native-sub-issue.py — e2e tests for issue #934.

When the loop shapes an item as `decomposition` (dispatch shape rank 3) and
files N per-feature child issues, it MUST establish the GitHub-native
parent/sub-issue link by passing `--parent <parent#>` to rabbit-issue's
`file-item.py` when filing each child, and it records the linkage in the
state's `decomposition_parents` map as a mirror. The GitHub-native sub-issue
rollup is the AUTHORITATIVE close-source; `decomposition_parents` is a
deprecating mirror honored during the coexistence window (a recorded parent
with no native sub-issues yet falls back to the hand-rolled per-child check).

This test covers two halves of the acceptance criteria:

  Part A (prescription) — the decomposition path the dispatcher follows
  prescribes `file-item.py … --parent <parent#>` for each child. Asserted
  against BOTH the source SKILL.md decomposition mechanics row and the spec
  Inv 53 text (the two surfaces that direct the dispatcher). Also asserts the
  GitHub-native sub-issue link is described and the state map is recorded.

  Part B (the link drives closing) — an end-to-end run of
  `close-decomposed-parents.py` with a PATH-resident `gh` shim: when the
  parent's GitHub-native sub-issue rollup shows every sub-issue complete the
  parent is closed and its `decomposition_parents` key dropped; the close
  decision reads the native rollup (`gh api repos/.../issues/<parent>` ->
  `sub_issues_summary`), not a per-child enumeration of the legacy map. This
  pins that the GitHub-native link is the close driver.

Fixtures for Part B: a PATH-resident `gh` shim answering
`gh api repos/<slug>/issues/<n>` from a baked sub_issues_summary table and
logging `gh issue close ...` calls; state_dir via
RABBIT_AUTO_EVOLVE_STATE_DIR.
"""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(HERE, ".."))
CLOSE_SCRIPT = os.path.join(FEATURE_DIR, "scripts", "close-decomposed-parents.py")
SKILL_MD = os.path.join(
    FEATURE_DIR, "skills", "rabbit-auto-evolve", "SKILL.md")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec.md")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# ---------------------------------------------------------------------------
# Part A — the decomposition path prescribes file-item.py --parent <parent#>.
# ---------------------------------------------------------------------------

def _decomposition_row(text):
    """Return the SKILL.md decomposition mechanics table row (the line whose
    shape cell is `decomposition`), or '' if not found."""
    for line in text.splitlines():
        low = line.lower()
        if "`decomposition`" in low and "file-item.py" in low:
            return line
    return ""


skill_text = open(SKILL_MD).read()
spec_text = open(SPEC_MD).read()
spec_low = re.sub(r"\s+", " ", spec_text.lower())

row = _decomposition_row(skill_text)
if not row:
    fail("SKILL.md has no decomposition row invoking file-item.py")
else:
    low = row.lower()
    if "--parent" not in low:
        fail("SKILL.md decomposition row does not pass --parent to file-item.py "
             "(child not born as a GitHub-native sub-issue; #934)")
    else:
        ok("SKILL.md decomposition row passes --parent to file-item.py (#934)")

# The spec Inv 53 text must prescribe filing children with --parent too.
if "file-item.py --parent" not in spec_low and "--parent <parent#>" not in spec_low:
    fail("spec.md Inv 53 does not prescribe filing children with "
         "file-item.py --parent (#934)")
else:
    ok("spec.md Inv 53 prescribes file-item.py --parent for children (#934)")

# The GitHub-native sub-issue link/rollup must be named, and the state map
# recorded as a mirror — the close-source is the native rollup.
if "github-native" not in spec_low and "github native" not in spec_low:
    fail("spec.md Inv 53 does not mention the GitHub-native sub-issue link")
else:
    ok("spec.md Inv 53 mentions the GitHub-native sub-issue link")

if "decomposition_parents" not in spec_low:
    fail("spec.md Inv 53 does not mention decomposition_parents")
else:
    ok("spec.md Inv 53 records the decomposition_parents mirror")

if "sub_issues_summary" not in spec_low and "sub-issue rollup" not in spec_low:
    fail("spec.md Inv 53 does not name the GitHub-native sub-issue rollup as "
         "the close-source")
else:
    ok("spec.md Inv 53 names the GitHub-native sub-issue rollup the close-source")


# ---------------------------------------------------------------------------
# Part B — close-decomposed-parents.py drives closing from the GitHub-native
# sub-issue rollup (sub_issues_summary on the parent).
# ---------------------------------------------------------------------------

GH_SHIM = r"""#!/usr/bin/env python3
import json, os, re, sys
CALL_LOG = os.environ["GH_CALL_LOG"]
SUMMARIES = json.loads(os.environ["GH_PARENT_SUMMARIES"])
argv = sys.argv[1:]
with open(CALL_LOG, "a") as f:
    f.write(" ".join(argv) + "\n")
if len(argv) >= 2 and argv[0] == "api":
    m = re.match(r"repos/[^/]+/[^/]+/issues/(\d+)$", argv[1])
    if m:
        num = m.group(1)
        summ = SUMMARIES.get(num, {"total": 0, "completed": 0})
        print(json.dumps({"number": int(num), "sub_issues_summary": summ}))
        sys.exit(0)
    sys.exit(3)
if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "view":
    print(json.dumps({"state": "OPEN"}))
    sys.exit(0)
if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "close":
    sys.exit(0)
sys.exit(0)
"""


def _make_gh_shim(bindir, parent_summaries, call_log):
    path = os.path.join(bindir, "gh")
    with open(path, "w") as f:
        f.write(GH_SHIM)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP |
             stat.S_IXOTH)
    env = dict(os.environ)
    env["GH_CALL_LOG"] = call_log
    env["GH_PARENT_SUMMARIES"] = json.dumps(parent_summaries)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    return env


def _seed_state(state_dir, decomposition_parents):
    state = {
        "schema_version": "1.4.0",
        "updated_at": "2026-06-04T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "decomposition_parents": decomposition_parents,
    }
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f, indent=2)


def _read_state(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        return json.load(f)


def _run_close(state_dir, env):
    return subprocess.run(
        [sys.executable, CLOSE_SCRIPT],
        capture_output=True, text=True, env=env)


with tempfile.TemporaryDirectory() as td:
    state_dir = os.path.join(td, ".rabbit")
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    call_log = os.path.join(td, "gh-calls.log")

    # Parent 100 native rollup 2/2 complete -> parent closes, key drops.
    # Parent 200 native rollup 0/1 complete -> parent untouched, key retained.
    _seed_state(state_dir, {"100": [101, 102], "200": [201]})
    env = _make_gh_shim(
        bindir,
        {"100": {"total": 2, "completed": 2},
         "200": {"total": 1, "completed": 0}},
        call_log)
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir

    proc = _run_close(state_dir, env)
    if proc.returncode != 0:
        fail(f"close-decomposed-parents.py exited {proc.returncode}: "
             f"{proc.stderr}")
    else:
        ok("close-decomposed-parents.py ran cleanly")

    state = _read_state(state_dir)
    dp = state.get("decomposition_parents", {})

    # The complete-rollup parent (100) is closed and dropped from the map.
    if "100" in dp:
        fail("parent 100 (native rollup complete) was NOT dropped from "
             "decomposition_parents")
    else:
        ok("parent 100 dropped from decomposition_parents after its native "
           "rollup showed all sub-issues complete")

    # The incomplete-rollup parent (200) is retained.
    if dp.get("200") != [201]:
        fail("parent 200 (rollup incomplete) was not retained in "
             "decomposition_parents")
    else:
        ok("parent 200 retained (native rollup incomplete)")

    log = open(call_log).read() if os.path.exists(call_log) else ""
    if "issue close 100" not in log:
        fail("gh issue close was not invoked for parent 100")
    else:
        ok("gh issue close invoked for parent 100")
    if "issue close 200" in log:
        fail("gh issue close was wrongly invoked for parent 200 (rollup "
             "incomplete)")
    else:
        ok("parent 200 not closed (rollup incomplete)")

    # The close driver read the GitHub-native sub-issue rollup on the parent
    # (gh api repos/.../issues/100), confirming the native rollup, not a
    # per-child enumeration of the legacy map, is the close-source.
    if "api repos/" not in log or "/issues/100" not in log:
        fail("close path did not read the GitHub-native sub-issue rollup for "
             "parent 100 (gh api repos/.../issues/100)")
    else:
        ok("close path read the GitHub-native sub-issue rollup (native rollup "
           "is the authoritative close-source)")


sys.exit(FAIL)
