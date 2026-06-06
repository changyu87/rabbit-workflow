#!/usr/bin/env python3
"""test-authoritative-version.py — rabbit-auto-evolve Inv 64 (issue #986).

#986 (bug): on the CronCreate session-reuse path the dispatcher session is
REUSED across ticks and context ACCUMULATES (Inv 33), so the evolver narrated
a STALE version (kept citing an old `vX.Y.Z`) anchored in old context — even
though the authoritative state (`auto-evolve-state.json` `last_tagged_version`)
and `git describe --tags` were correct/current. The stale string lived ONLY in
accumulated session context, no persistent artifact.

The fix grounds version narration in the AUTHORITATIVE current version,
surfaced FRESH each tick in the tick-exit / schedule-decision output so any
narrator reads it from a deterministic source rather than from memory.

`scripts/schedule-decision.py` (the end-of-tick / heartbeat schedule output)
now emits an `authoritative_version` field resolved FRESH every tick from
`git describe --tags --abbrev=0`, falling back to the state
`last_tagged_version`, falling back to null. NEVER a value carried in
accumulated session context.

This e2e exercises the shipped `schedule-decision.py` surface end-to-end via
the env injection points:

  - RABBIT_AUTO_EVOLVE_GIT_DESCRIBE_CMD : a shim emitting the git-describe
    output (so no real `git` is shelled out), and
  - RABBIT_AUTO_EVOLVE_STATE_DIR        : the state dir holding
    auto-evolve-state.json (for the fallback).

Scenarios:
  A) git-describe resolves -> authoritative_version is that FRESH value
     (idle and immediate-refire paths both carry it).
  B) STALE cached state value present BUT git-describe resolves a DIFFERENT
     (current) value -> the surfaced field reflects the git-describe
     authoritative source, NOT the stale cached value.
  C) git-describe unavailable (shim exits non-zero) -> falls back to the
     state `last_tagged_version`.
  D) neither git-describe nor state -> authoritative_version is null
     (honest absence, never fabricated).
  E) spec.md carries the Inv 64 narration-grounding invariant text and the
     four versioned artifacts are bumped in lockstep (Inv 15).
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FEATURE_DIR = HERE.parent
SCRIPTS = FEATURE_DIR / "scripts"
DECIDE = SCRIPTS / "schedule-decision.py"
REPO_ROOT = FEATURE_DIR.parents[2]

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "contract.md"
FEATURE_JSON = FEATURE_DIR / "feature.json"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _make_fetch_shim(dirpath, json_array):
    shim = os.path.join(dirpath, "fetch-queue-shim.py")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import json, sys
            json.dump({json.dumps(json_array)}, sys.stdout)
            sys.exit(0)
        """))
    return shim


def _make_git_describe_shim(dirpath, value, exit_code=0):
    """A shim standing in for `git describe --tags --abbrev=0`: prints `value`
    on stdout and exits `exit_code`. exit_code != 0 simulates no tags."""
    shim = os.path.join(dirpath, "git-describe-shim.py")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            sys.stdout.write({value!r})
            sys.exit({exit_code})
        """))
    return shim


def _write_state(state_dir, obj):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(obj, f)


def _run_decide(*, fetch_array, git_describe_value=None, git_describe_exit=0,
                state=None):
    """Run schedule-decision.py with injected fetch-queue + git-describe shims
    and an isolated state dir. Returns the parsed JSON decision."""
    with tempfile.TemporaryDirectory() as td:
        env = os.environ.copy()
        env["RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD"] = _make_fetch_shim(td, fetch_array)
        env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = td
        if git_describe_value is not None:
            shim = _make_git_describe_shim(td, git_describe_value, git_describe_exit)
            env["RABBIT_AUTO_EVOLVE_GIT_DESCRIBE_CMD"] = f"{sys.executable} {shim}"
        else:
            # Force the no-git path explicitly so the test never shells out to
            # the real repo's git.
            env["RABBIT_AUTO_EVOLVE_GIT_DESCRIBE_CMD"] = "false"
        if state is not None:
            _write_state(td, state)
        proc = subprocess.run(
            [sys.executable, str(DECIDE)],
            env=env, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            fail(f"schedule-decision exited {proc.returncode}; stderr={proc.stderr!r}")
            return None
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"stdout not JSON: {e}; stdout={proc.stdout!r}")
            return None


# --- A) git-describe resolves -> the FRESH value, both decision paths ---
for label, fetch in (("idle", []), ("immediate-refire", [{"issue": 1}])):
    res = _run_decide(fetch_array=fetch, git_describe_value="v10.5.3\n")
    if res is None:
        continue
    if "authoritative_version" not in res:
        fail(f"A/{label}: decision lacks authoritative_version field: {res!r}")
    elif res["authoritative_version"] != "v10.5.3":
        fail(f"A/{label}: expected authoritative_version 'v10.5.3', got "
             f"{res['authoritative_version']!r}")
    else:
        ok(f"A/{label}: authoritative_version is the FRESH git-describe value")


# --- B) STALE cached state value but git-describe wins ---
res = _run_decide(
    fetch_array=[],
    git_describe_value="v10.5.3\n",
    state={"last_tagged_version": "v10.1.1"},  # the #986 stale narration value
)
if res is not None:
    if res.get("authoritative_version") == "v10.5.3":
        ok("B: git-describe authoritative value overrides the stale cached "
           "state value (v10.1.1 -> v10.5.3)")
    elif res.get("authoritative_version") == "v10.1.1":
        fail("B: surfaced the STALE cached value v10.1.1 instead of the "
             "authoritative git-describe value v10.5.3 (#986 regression)")
    else:
        fail(f"B: unexpected authoritative_version "
             f"{res.get('authoritative_version')!r}")


# --- C) git-describe unavailable -> fall back to state last_tagged_version ---
res = _run_decide(
    fetch_array=[],
    git_describe_value="",
    git_describe_exit=1,  # no tags / git fails
    state={"last_tagged_version": "v10.5.3"},
)
if res is not None:
    if res.get("authoritative_version") == "v10.5.3":
        ok("C: falls back to state last_tagged_version when git-describe fails")
    else:
        fail(f"C: expected fallback to state value 'v10.5.3', got "
             f"{res.get('authoritative_version')!r}")


# --- D) neither source -> null (honest absence) ---
res = _run_decide(fetch_array=[], git_describe_value="", git_describe_exit=1)
if res is not None:
    if res.get("authoritative_version") is None:
        ok("D: authoritative_version is null when neither git nor state resolves")
    else:
        fail(f"D: expected null authoritative_version, got "
             f"{res.get('authoritative_version')!r}")


# --- D2: the pure resolver is importable ---
spec = importlib.util.spec_from_file_location("schedule_decision", DECIDE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if hasattr(mod, "resolve_authoritative_version"):
    ok("D2: schedule-decision exposes resolve_authoritative_version()")
else:
    fail("D2: schedule-decision does not expose resolve_authoritative_version()")


# --- E) spec carries Inv 64 + four-way version lockstep ---
spec_low = SPEC_MD.read_text().lower()
SPEC_REQUIRED = [
    "authoritative",
    "git describe",
    "last_tagged_version",
    "schedule-decision.py",
    "accumulated session context",
]
missing = [s for s in SPEC_REQUIRED if s not in spec_low]
if missing:
    fail(f"E: spec.md missing Inv 64 phrase(s): {missing!r}")
else:
    ok("E: spec.md carries the authoritative-version narration-grounding "
       "invariant (Inv 64)")

# The invariant describes the CronCreate session-reuse failure by BEHAVIOR,
# not by an issue tag — the spec is a housekeeping-clean surface so #NNN tags
# belong only in CHANGELOG / commit messages (contract Inv 41).
inv64 = SPEC_MD.read_text().lower()
if "session-reuse" in inv64 and "croncreate" in inv64:
    ok("E: spec.md describes the CronCreate session-reuse failure behaviorally")
else:
    fail("E: spec.md Inv 64 does not describe the session-reuse failure mode")
if "#986" not in SPEC_MD.read_text():
    ok("E: spec.md carries no #NNN issue tag (housekeeping-clean surface)")
else:
    fail("E: spec.md carries a #NNN tag — forbidden on a clean doc surface")


def _frontmatter_version(path):
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$",
                  path.read_text(), re.MULTILINE)
    return m.group(1) if m else None


versions = {
    "feature.json": json.loads(FEATURE_JSON.read_text()).get("version"),
    "spec.md": _frontmatter_version(SPEC_MD),
    "contract.md": _frontmatter_version(CONTRACT_MD),
    "SKILL.md": _frontmatter_version(SOURCE_SKILL),
}
if None in versions.values():
    fail(f"E: could not parse version from all artifacts: {versions!r}")
elif len(set(versions.values())) == 1:
    ok(f"E: all four versioned artifacts in lockstep at "
       f"{next(iter(versions.values()))} (Inv 15)")
else:
    fail(f"E: version drift across artifacts: {versions!r}")


sys.exit(FAIL)
