#!/usr/bin/env python3
"""test-classify-merge-restart.py — e2e tests for scripts/classify-merge-restart.py (Inv 8).

Covers the spec'd surface of `scripts/classify-merge-restart.py`:
  - --help smoke
  - restart from a settings.json touch
  - restart from a brand-new .claude/skills/foo/SKILL.md add
    (additions > 0 AND deletions == 0)
  - restart from a .claude/hooks/bar.py modification
  - restart from a brand-new .claude/agents/foo.md add (#537)
  - restart from a .claude/agents/foo.md modification (#537)
  - refresh from .claude/features/policy/coding-rules.md
  - refresh from CLAUDE.md touch
  - no-op from an arbitrary feature-local script touch
  - precedence: settings.json + policy file → restart (not refresh)

Fixture pattern: tempdir on PATH carrying a `gh` shim that responds to
`gh pr view <#> --json files` by echoing a per-test JSON payload sourced
from the GH_SHIM_FIXTURE env var.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "classify-merge-restart.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_gh_shim(shim_dir):
    """gh shim: echoes the JSON in $GH_SHIM_FIXTURE on `gh pr view ... --json files`."""
    shim = os.path.join(shim_dir, "gh")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        f.write('cat "$GH_SHIM_FIXTURE"\n')
        f.write('exit 0\n')
    os.chmod(shim, stat.S_IRWXU)


def _run(files_payload, extra_args=None):
    """Invoke the script with a fixture file list; return (proc, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as shim_dir:
        _write_gh_shim(shim_dir)
        fixture_path = os.path.join(shim_dir, "fixture.json")
        with open(fixture_path, "w") as f:
            json.dump({"files": files_payload}, f)

        env = os.environ.copy()
        env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
        env["GH_SHIM_FIXTURE"] = fixture_path

        args = [sys.executable, SCRIPT]
        if extra_args:
            args.extend(extra_args)
        else:
            args.append("123")
        proc = subprocess.run(args, capture_output=True, text=True, env=env)
        return proc


def _file(path, additions=1, deletions=0):
    return {"path": path, "additions": additions, "deletions": deletions}


# ---------------------------------------------------------------------------
# Scenario A — --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"A: --help should exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("A: --help exited 0")
help_text = (proc.stdout + proc.stderr).lower()
if "usage" not in help_text:
    fail(f"A: --help output should contain 'usage'; got stdout={proc.stdout!r} stderr={proc.stderr!r}")
else:
    ok("A: --help output contains 'usage'")


# ---------------------------------------------------------------------------
# Scenario B — restart from settings.json touch
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/settings.json", additions=2, deletions=1)])
if proc.returncode != 0:
    fail(f"B: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "restart\n":
    fail(f"B: expected 'restart\\n', got {proc.stdout!r}")
else:
    ok("B: settings.json touch → restart")


# ---------------------------------------------------------------------------
# Scenario C — restart from brand-new SKILL.md add (additions>0, deletions==0)
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/skills/foo/SKILL.md", additions=42, deletions=0)])
if proc.returncode != 0:
    fail(f"C: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "restart\n":
    fail(f"C: expected 'restart\\n', got {proc.stdout!r}")
else:
    ok("C: brand-new SKILL.md → restart")


# ---------------------------------------------------------------------------
# Scenario C2 — SKILL.md with deletions > 0 must NOT trigger restart
# (modification, not pure-add; should fall through to no-op)
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/skills/foo/SKILL.md", additions=5, deletions=3)])
if proc.returncode != 0:
    fail(f"C2: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "no-op\n":
    fail(f"C2: SKILL.md modification (not pure-add) should be no-op, got {proc.stdout!r}")
else:
    ok("C2: SKILL.md modification (deletions > 0) → no-op (not restart)")


# ---------------------------------------------------------------------------
# Scenario D — restart from .claude/hooks/bar.py modification
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/hooks/bar.py", additions=3, deletions=2)])
if proc.returncode != 0:
    fail(f"D: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "restart\n":
    fail(f"D: expected 'restart\\n', got {proc.stdout!r}")
else:
    ok("D: .claude/hooks/bar.py touch → restart")


# ---------------------------------------------------------------------------
# Scenario D2 — restart from a brand-new .claude/agents/foo.md add (#537)
# Agent definitions load at session start, so an added agent def needs a
# restart to take effect.
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/agents/foo.md", additions=30, deletions=0)])
if proc.returncode != 0:
    fail(f"D2: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "restart\n":
    fail(f"D2: brand-new .claude/agents/foo.md should be restart, got {proc.stdout!r}")
else:
    ok("D2: brand-new .claude/agents/foo.md → restart")


# ---------------------------------------------------------------------------
# Scenario D3 — restart from a .claude/agents/foo.md modification (#537)
# Unlike SKILL.md, an agent-def MODIFICATION also requires a restart, since
# the existing definition is already loaded into the running session.
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/agents/foo.md", additions=4, deletions=6)])
if proc.returncode != 0:
    fail(f"D3: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "restart\n":
    fail(f"D3: modified .claude/agents/foo.md should be restart, got {proc.stdout!r}")
else:
    ok("D3: modified .claude/agents/foo.md → restart")


# ---------------------------------------------------------------------------
# Scenario E — refresh from .claude/features/policy/coding-rules.md
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/features/policy/coding-rules.md", additions=1, deletions=0)])
if proc.returncode != 0:
    fail(f"E: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "refresh\n":
    fail(f"E: expected 'refresh\\n', got {proc.stdout!r}")
else:
    ok("E: policy/*.md touch → refresh")


# ---------------------------------------------------------------------------
# Scenario F — refresh from CLAUDE.md touch
# ---------------------------------------------------------------------------
proc = _run([_file("CLAUDE.md", additions=1, deletions=1)])
if proc.returncode != 0:
    fail(f"F: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "refresh\n":
    fail(f"F: expected 'refresh\\n', got {proc.stdout!r}")
else:
    ok("F: CLAUDE.md touch → refresh")


# Also accept CLAUDE.md at any depth (basename match per spec).
proc = _run([_file(".claude/features/foo/CLAUDE.md", additions=1, deletions=0)])
if proc.returncode != 0:
    fail(f"F2: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "refresh\n":
    fail(f"F2: expected 'refresh\\n' for deep CLAUDE.md, got {proc.stdout!r}")
else:
    ok("F2: CLAUDE.md at depth → refresh")


# ---------------------------------------------------------------------------
# Scenario G — no-op from an arbitrary feature-local script touch
# ---------------------------------------------------------------------------
proc = _run([_file(".claude/features/other-feature/scripts/x.py", additions=10, deletions=2)])
if proc.returncode != 0:
    fail(f"G: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "no-op\n":
    fail(f"G: expected 'no-op\\n', got {proc.stdout!r}")
else:
    ok("G: arbitrary feature script → no-op")


# ---------------------------------------------------------------------------
# Scenario H — precedence: settings.json + policy file → restart (not refresh)
# ---------------------------------------------------------------------------
proc = _run([
    _file(".claude/settings.json", additions=1, deletions=0),
    _file(".claude/features/policy/coding-rules.md", additions=2, deletions=0),
])
if proc.returncode != 0:
    fail(f"H: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout != "restart\n":
    fail(f"H: precedence — settings + policy should yield restart, got {proc.stdout!r}")
else:
    ok("H: precedence restart > refresh honored")


sys.exit(FAIL)
