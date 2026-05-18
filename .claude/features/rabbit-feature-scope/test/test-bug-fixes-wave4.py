#!/usr/bin/env python3
# test-bug-fixes-wave4.py — e2e tests for Wave 4 bug/backlog closures.
#
# Covers:
#   BUG-4   resolve-scope.py propagates errors from subprocess invocations
#   BUG-6   resolve-scope.py emits actionable error when RABBIT_ROOT unset and not in git
#   BUG-18  feature.json surface.skills lists rabbit-feature-scope
#   BUG-20  SKILL.md Notes references correct find-feature.py invocation (list-json subcommand)
#   BUG-22  resolve-scope.py exits 2 on invocation error (contract)
#   BACKLOG-2 format-feature-context.py emits tdd_state
#   BACKLOG-4 resolve-scope.py supports --help / -h
#   BACKLOG-6 resolve-scope.py supports --verbose / -v
#   BACKLOG-7 format-feature-context.py docstring includes input schema

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
script = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/resolve-scope.py"
helper = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/format-feature-context.py"
feature_json = Path(repo_root) / ".claude/features/rabbit-feature-scope/feature.json"
skill_md = Path(repo_root) / ".claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md"

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


# ---------------------------------------------------------------------------
# BUG-4: resolve-scope.py must propagate errors from subprocess invocations.
# Strategy: invoke resolve-scope.py with RABBIT_ROOT pointing at a directory
# that has a broken find-feature.py (one that exits non-zero). The script
# must emit a stderr message and exit non-zero rather than silently producing
# an empty REGISTERED FEATURES block.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    fake_root = Path(td)
    fake_ff = fake_root / ".claude/features/contract/scripts/find-feature.py"
    fake_ff.parent.mkdir(parents=True)
    fake_ff.write_text("#!/usr/bin/env python3\nimport sys\nsys.stderr.write('boom\\n')\nsys.exit(1)\n")
    fake_ff.chmod(0o755)
    env = os.environ.copy()
    env["RABBIT_ROOT"] = str(fake_root)
    res = subprocess.run(
        [sys.executable, str(script), "test bug4"],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0 and res.stderr.strip():
        ok("BUG-4: find-feature.py failure propagated to stderr + non-zero exit")
    else:
        fail(f"BUG-4: subprocess failure was swallowed; rc={res.returncode}, stderr={res.stderr!r}")

# Same shape for format-feature-context.py failures: feed find-feature.py
# output that the formatter rejects, expect non-zero exit + stderr.
with tempfile.TemporaryDirectory() as td:
    fake_root = Path(td)
    fake_ff = fake_root / ".claude/features/contract/scripts/find-feature.py"
    fake_ff.parent.mkdir(parents=True)
    # find-feature.py outputs a JSON object that lacks the required 'name' key
    # in its sole entry. format-feature-context.py rejects that with exit 1.
    fake_ff.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('[{\"path\":\"x\",\"summary\":\"y\"}]')\n"
    )
    fake_ff.chmod(0o755)
    env = os.environ.copy()
    env["RABBIT_ROOT"] = str(fake_root)
    res = subprocess.run(
        [sys.executable, str(script), "test bug4 formatter"],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0 and res.stderr.strip():
        ok("BUG-4: format-feature-context.py failure propagated to stderr + non-zero exit")
    else:
        fail(f"BUG-4: formatter failure was swallowed; rc={res.returncode}, stderr={res.stderr!r}")

# ---------------------------------------------------------------------------
# BUG-6: when RABBIT_ROOT is unset AND the script is not in a git repo,
# the error message must be actionable — mention RABBIT_ROOT explicitly.
# Strategy: copy resolve-scope.py into /tmp (no git) and invoke without RABBIT_ROOT.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    iso = Path(td) / "isolated"
    iso.mkdir()
    target = iso / "resolve-scope.py"
    target.write_bytes(script.read_bytes())
    target.chmod(0o755)
    # Also copy format-feature-context.py so script can locate it normally.
    target_helper = iso / "format-feature-context.py"
    target_helper.write_bytes(helper.read_bytes())
    target_helper.chmod(0o755)
    env = os.environ.copy()
    env.pop("RABBIT_ROOT", None)
    res = subprocess.run(
        [sys.executable, str(target), "test bug6"],
        capture_output=True, text=True, env=env, cwd=str(iso),
    )
    if res.returncode != 0 and "RABBIT_ROOT" in res.stderr:
        ok("BUG-6: error message names RABBIT_ROOT when unset and not in git repo")
    else:
        fail(f"BUG-6: missing actionable error; rc={res.returncode}, stderr={res.stderr!r}")

# ---------------------------------------------------------------------------
# BUG-18: feature.json surface.skills MUST list the rabbit-feature-scope skill.
# ---------------------------------------------------------------------------
with open(feature_json) as f:
    fj = json.load(f)
skills_listed = fj.get("surface", {}).get("skills", [])
if any("rabbit-feature-scope" in s for s in skills_listed):
    ok(f"BUG-18: feature.json surface.skills lists the skill: {skills_listed}")
else:
    fail(f"BUG-18: feature.json surface.skills missing rabbit-feature-scope: {skills_listed}")

# ---------------------------------------------------------------------------
# BUG-20: SKILL.md Notes section must reference the correct find-feature.py
# invocation. The current code uses subcommand `list-json` (not flag --list-json).
# Assert the subcommand wording matches.
# ---------------------------------------------------------------------------
skill_text = skill_md.read_text()
# Locate the Notes section
notes_start = skill_text.find("## Notes")
notes_section = skill_text[notes_start:] if notes_start != -1 else ""
if "find-feature.py list-json" in notes_section or "find-feature.py` `list-json" in notes_section:
    ok("BUG-20: Notes section references 'find-feature.py list-json' subcommand")
else:
    fail("BUG-20: Notes section uses wrong find-feature.py interface (must say 'list-json' subcommand)")

# ---------------------------------------------------------------------------
# BUG-22: contract says exit 2 on invocation error. Already tested in
# test-resolve-scope.py but re-asserted here as part of the wave-4 set.
# ---------------------------------------------------------------------------
res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
if res.returncode == 2:
    ok("BUG-22: resolve-scope.py exits 2 on missing-arg invocation error")
else:
    fail(f"BUG-22: expected exit 2, got {res.returncode}")

# Bad flag should also be invocation error -> exit 2.
res = subprocess.run([sys.executable, str(script), "--nonexistent-flag", "x"], capture_output=True, text=True)
if res.returncode == 2:
    ok("BUG-22: unknown flag is invocation error -> exit 2")
else:
    fail(f"BUG-22: unknown flag expected exit 2, got {res.returncode}")

# ---------------------------------------------------------------------------
# BACKLOG-2: format-feature-context.py emits tdd_state when present in input.
# ---------------------------------------------------------------------------
sample = json.dumps([{
    "name": "feat-x",
    "path": ".claude/features/feat-x",
    "summary": "does X",
    "tdd_state": "test-green",
}])
res = subprocess.run(
    [sys.executable, str(helper)], input=sample, capture_output=True, text=True,
)
if "test-green" in res.stdout:
    ok("BACKLOG-2: format-feature-context.py emits tdd_state in output")
else:
    fail(f"BACKLOG-2: tdd_state missing from output: {res.stdout!r}")

# When tdd_state absent, must still succeed (Inv 11 — optional key).
sample = json.dumps([{"name": "feat-y"}])
res = subprocess.run(
    [sys.executable, str(helper)], input=sample, capture_output=True, text=True,
)
if res.returncode == 0:
    ok("BACKLOG-2: tdd_state absence still succeeds")
else:
    fail(f"BACKLOG-2: missing tdd_state caused failure: rc={res.returncode}")

# ---------------------------------------------------------------------------
# BACKLOG-4: resolve-scope.py supports --help / -h.
# ---------------------------------------------------------------------------
for flag in ("--help", "-h"):
    res = subprocess.run(
        [sys.executable, str(script), flag], capture_output=True, text=True,
    )
    # argparse prints help to stdout and exits 0
    if res.returncode == 0 and ("usage" in res.stdout.lower() or "usage" in res.stderr.lower()):
        ok(f"BACKLOG-4: resolve-scope.py {flag} prints usage and exits 0")
    else:
        fail(f"BACKLOG-4: {flag} broken; rc={res.returncode}, stdout={res.stdout[:200]!r}")

# ---------------------------------------------------------------------------
# BACKLOG-6: resolve-scope.py supports --verbose / -v for debugging.
# When verbose, the script must emit some progress/debug info to stderr.
# ---------------------------------------------------------------------------
for flag in ("--verbose", "-v"):
    res = subprocess.run(
        [sys.executable, str(script), flag, "test backlog 6"],
        capture_output=True, text=True,
    )
    if res.returncode == 0 and res.stderr.strip():
        ok(f"BACKLOG-6: {flag} emits debug info to stderr")
    else:
        fail(f"BACKLOG-6: {flag} produced no stderr or non-zero exit; rc={res.returncode}")

# ---------------------------------------------------------------------------
# BACKLOG-7: format-feature-context.py docstring includes input schema.
# ---------------------------------------------------------------------------
helper_text = helper.read_text()
# Module docstring/header must reference the input JSON shape — i.e. mention
# the recognized keys: 'name', 'path', 'summary', 'tdd_state'.
header_block = helper_text[:1500]
required_keys = ["name", "path", "summary", "tdd_state"]
missing_keys = [k for k in required_keys if k not in header_block]
if not missing_keys:
    ok("BACKLOG-7: format-feature-context.py header documents input schema keys")
else:
    fail(f"BACKLOG-7: header missing schema keys: {missing_keys}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
