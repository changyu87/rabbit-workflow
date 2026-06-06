#!/usr/bin/env python3
"""test-decomposition-native-sub-issue.py — e2e tests for issue #934.

When the loop shapes an item as `decomposition` (dispatch shape rank 3) and
files N per-feature child issues, it MUST ALSO establish the GitHub-native
parent/sub-issue link by passing `--parent <parent#>` to rabbit-issue's
`file-item.py` when filing each child — while keeping the internal state map
(`decomposition_parents`) authoritative (Machine First). The GitHub-native
link is a DERIVATIVE human-readable view; it must NOT replace the state map,
and `close-decomposed-parents.py` keeps driving parent-closing off
`decomposition_parents` (closing behavior unchanged).

This test covers two halves of the acceptance criteria:

  Part A (prescription) — the decomposition path the dispatcher follows
  prescribes `file-item.py … --parent <parent#>` for each child. Asserted
  against BOTH the source SKILL.md decomposition mechanics row and the spec
  Inv 53 text (the two surfaces that direct the dispatcher). Also asserts the
  state map is named the authoritative source on both surfaces.

  Part B (state map is still the close driver) — an end-to-end run of
  `close-decomposed-parents.py` against a seeded `decomposition_parents` map
  with a PATH-resident `gh` shim: when every recorded child is CLOSED the
  parent is closed and its key dropped; the close decision is driven SOLELY
  from `decomposition_parents`, never from the GitHub-native sub-issue link.
  This pins that #934's derivative GitHub link did not displace the
  authoritative map as the close driver.

Fixtures for Part B mirror test-close-decomposed-parents.py: a PATH-resident
`gh` shim answering `gh issue view <n> --json state` from a baked table and
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

# The GitHub-native link must be named a DERIVATIVE view; the state map must be
# named AUTHORITATIVE — the link must not be presented as replacing the map.
if "github-native" not in spec_low and "github native" not in spec_low:
    fail("spec.md Inv 53 does not mention the GitHub-native sub-issue link (#934)")
else:
    ok("spec.md Inv 53 mentions the GitHub-native sub-issue link (#934)")

if "authoritative" not in spec_low or "decomposition_parents" not in spec_low:
    fail("spec.md Inv 53 does not name decomposition_parents as authoritative")
else:
    ok("spec.md Inv 53 names decomposition_parents authoritative (state map "
       "stays the source of truth; #934)")

if "derivative" not in spec_low:
    fail("spec.md Inv 53 does not frame the GitHub-native link as derivative")
else:
    ok("spec.md Inv 53 frames the GitHub-native link as a derivative view")


# ---------------------------------------------------------------------------
# Part B — close-decomposed-parents.py still drives closing from the state map.
# ---------------------------------------------------------------------------

GH_SHIM = """#!/usr/bin/env python3
import json, os, sys
CALL_LOG = os.environ["GH_CALL_LOG"]
STATE_TABLE = json.loads(os.environ["GH_CHILD_STATES"])
argv = sys.argv[1:]
with open(CALL_LOG, "a") as f:
    f.write(" ".join(argv) + "\\n")
if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "view":
    num = argv[2]
    state = STATE_TABLE.get(num, "OPEN")
    print(json.dumps({"state": state}))
    sys.exit(0)
if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "close":
    sys.exit(0)
sys.exit(0)
"""


def _make_gh_shim(bindir, child_states, call_log):
    path = os.path.join(bindir, "gh")
    with open(path, "w") as f:
        f.write(GH_SHIM)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP |
             stat.S_IXOTH)
    env = dict(os.environ)
    env["GH_CALL_LOG"] = call_log
    env["GH_CHILD_STATES"] = json.dumps(child_states)
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

    # Parent 100 has children 101,102 — both CLOSED -> parent closes, key drops.
    # Parent 200 has child 201 still OPEN -> parent untouched, key retained.
    _seed_state(state_dir, {"100": [101, 102], "200": [201]})
    env = _make_gh_shim(
        bindir,
        {"101": "CLOSED", "102": "CLOSED", "201": "OPEN"},
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

    # The all-closed parent (100) is closed and dropped FROM THE STATE MAP.
    if "100" in dp:
        fail("parent 100 (all children closed) was NOT dropped from "
             "decomposition_parents — the state map is the close driver")
    else:
        ok("parent 100 dropped from decomposition_parents after all children "
           "closed (state map drives the close)")

    # The parent with an open child (200) is retained.
    if dp.get("200") != [201]:
        fail("parent 200 (child still open) was not retained in "
             "decomposition_parents")
    else:
        ok("parent 200 retained (child still open)")

    log = open(call_log).read() if os.path.exists(call_log) else ""
    if "issue close 100" not in log:
        fail("gh issue close was not invoked for parent 100")
    else:
        ok("gh issue close invoked for parent 100")
    if "issue close 200" in log:
        fail("gh issue close was wrongly invoked for parent 200 (open child)")
    else:
        ok("parent 200 not closed (open child)")

    # The close driver consulted the children listed in decomposition_parents
    # (gh issue view of 101/102/201), NOT a GitHub-native sub-issue lookup of
    # the parent — confirming the state map, not the derivative GitHub link, is
    # the authoritative source the close path reads.
    if "issue view 101" not in log or "issue view 102" not in log:
        fail("close path did not enumerate parent 100's recorded children "
             "from decomposition_parents")
    else:
        ok("close path enumerated children from decomposition_parents (state "
           "map authoritative; GitHub-native link not consulted; #934)")


sys.exit(FAIL)
