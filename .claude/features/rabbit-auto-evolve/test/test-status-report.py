#!/usr/bin/env python3
"""test-status-report.py — spec Inv 29 (added v0.17.0 for issue #405).

`scripts/status-report.py` is the deterministic backing script for the
read-only `status` subcommand. It reads ONLY
`.rabbit/auto-evolve-state.json` (defaults on missing/empty/malformed) and
the five runtime markers (`os.path.exists`), and emits a single fixed-format
JSON object on stdout. Exit code is 0 on every path (including the defaults
paths); non-zero is reserved for genuine invocation errors.

Output schema:
  {
    "queue_length": <int>,
    "in_flight": [<int>, ...],
    "last_merged_sha": <str|null>,
    "last_tagged_version": <str|null>,
    "consecutive_failures": <int>,
    "markers_present": [<sorted marker basenames>],
    "state_file": "present" | "absent" | "malformed"
  }

The script honors RABBIT_AUTO_EVOLVE_REPO_ROOT for test isolation.

This test also asserts the SKILL surface (Inv 29): the `status` section of
both the source and deployed SKILL.md invokes the script and contains no
bare `ls .rabbit-auto-evolve-*` pattern.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "status-report.py"
REPO_ROOT = FEATURE_DIR.parents[2]  # .../<repo>/.claude/features/rabbit-auto-evolve -> repo
SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

MARKERS = [
    ".rabbit-auto-evolve-active",
    ".rabbit-auto-evolve-running",
    ".rabbit-auto-evolve-stop-requested",
    ".rabbit-auto-evolve-restart-needed",
    ".rabbit-auto-evolve-aborted",
]

EXPECTED_KEYS = {
    "queue_length",
    "in_flight",
    "last_merged_sha",
    "last_tagged_version",
    "consecutive_failures",
    "markers_present",
    "state_file",
}


pass_n = 0
fail_n = 0


def ok(t: str, msg: str) -> None:
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t: str, msg: str) -> None:
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


def _run(repo_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


def _write_state(td: Path, obj: dict) -> None:
    state_dir = td / ".rabbit"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "auto-evolve-state.json").write_text(json.dumps(obj))


print("test-status-report.py")

# --- t1: script exists on disk ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")

# --- t2: --help smoke test ---
if SCRIPT.is_file():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        fail_t("help", f"--help exit {r.returncode}; stderr={r.stderr!r}")
    elif "usage" not in r.stdout.lower():
        fail_t("help", f"--help output lacks usage text: {r.stdout!r}")
    else:
        ok("help", "--help exits 0 with usage text")

# --- t3: known-state fixture: every field reflects the seeded state ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        state = {
            "schema_version": "1.1.0",
            "updated_at": "2026-06-03T00:00:00Z",
            "queue": [
                {"issue": 101, "decision": "work", "feature": "rabbit-auto-evolve"},
                {"issue": 102, "decision": "work", "feature": "contract"},
            ],
            "in_flight": [201, 202, 203],
            "last_merged_sha": "deadbeef1234",
            "last_tagged_version": "v0.5.3",
            "consecutive_failures": 2,
            "stop_requested": False,
            "restart_needed": None,
        }
        _write_state(td_path, state)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t("known/exit", f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}")
        else:
            try:
                rpt = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("known/json", f"stdout not JSON: {e}; stdout={r.stdout!r}")
                rpt = None
            if rpt is not None:
                missing = EXPECTED_KEYS - set(rpt.keys())
                if missing:
                    fail_t("known/keys", f"output missing keys: {sorted(missing)}")
                else:
                    ok("known/keys", "all expected keys present")
                checks = {
                    "queue_length": 2,
                    "in_flight": [201, 202, 203],
                    "last_merged_sha": "deadbeef1234",
                    "last_tagged_version": "v0.5.3",
                    "consecutive_failures": 2,
                    "state_file": "present",
                }
                bad = {k: (rpt.get(k), v) for k, v in checks.items() if rpt.get(k) != v}
                if bad:
                    fail_t("known/values", f"field mismatches (got, want): {bad}")
                else:
                    ok("known/values", "all field values match seeded state")
                if rpt.get("markers_present") != []:
                    fail_t(
                        "known/markers",
                        f"expected markers_present=[] (no markers), got "
                        f"{rpt.get('markers_present')!r}",
                    )
                else:
                    ok("known/markers", "markers_present=[] when no markers present")

# --- t4: missing state file -> defaults, state_file=absent, exit 0 ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t("absent/exit", f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}")
        else:
            try:
                rpt = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("absent/json", f"stdout not JSON: {e}; stdout={r.stdout!r}")
                rpt = None
            if rpt is not None:
                defaults = {
                    "queue_length": 0,
                    "in_flight": [],
                    "last_merged_sha": None,
                    "last_tagged_version": None,
                    "consecutive_failures": 0,
                    "markers_present": [],
                    "state_file": "absent",
                }
                bad = {k: (rpt.get(k), v) for k, v in defaults.items() if rpt.get(k) != v}
                if bad:
                    fail_t("absent/defaults", f"defaults mismatch (got, want): {bad}")
                else:
                    ok("absent/defaults", "missing state file yields defaults, state_file=absent")

# --- t5: malformed state file -> defaults, state_file=malformed, exit 0 ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        (td_path / ".rabbit").mkdir()
        (td_path / ".rabbit" / "auto-evolve-state.json").write_text("not json {{{")
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "malformed/exit",
                f"expected exit 0 even on malformed state; got {r.returncode}; "
                f"stderr={r.stderr!r}",
            )
        else:
            try:
                rpt = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("malformed/json", f"stdout not JSON: {e}; stdout={r.stdout!r}")
                rpt = None
            if rpt is not None:
                if rpt.get("state_file") != "malformed":
                    fail_t(
                        "malformed/state_file",
                        f"expected state_file=malformed, got {rpt.get('state_file')!r}",
                    )
                else:
                    ok("malformed/state_file", "malformed state file reported as malformed")
                if rpt.get("queue_length") != 0 or rpt.get("in_flight") != []:
                    fail_t(
                        "malformed/defaults",
                        f"expected default queue/in_flight, got "
                        f"queue_length={rpt.get('queue_length')!r}, "
                        f"in_flight={rpt.get('in_flight')!r}",
                    )
                else:
                    ok("malformed/defaults", "malformed state file yields defaults")

# --- t6: marker subset detection (sorted markers_present) ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Seed three of the five markers (deliberately out of sort order).
        present = [
            ".rabbit-auto-evolve-running",
            ".rabbit-auto-evolve-active",
            ".rabbit-auto-evolve-aborted",
        ]
        for m in present:
            (td_path / m).write_text("session")
        r = _run(td_path)
        if r.returncode != 0:
            fail_t("markers/exit", f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}")
        else:
            try:
                rpt = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("markers/json", f"stdout not JSON: {e}; stdout={r.stdout!r}")
                rpt = None
            if rpt is not None:
                expect = sorted(present)
                if rpt.get("markers_present") != expect:
                    fail_t(
                        "markers/subset",
                        f"expected markers_present={expect}, got "
                        f"{rpt.get('markers_present')!r}",
                    )
                else:
                    ok("markers/subset", "markers_present is exactly the sorted seeded subset")

# --- t7: SKILL surface (source + deployed) invokes the script, no bare ls ---
INVOCATION = (
    "python3 .claude/features/rabbit-auto-evolve/scripts/status-report.py"
)


def _status_section(text: str) -> str:
    """Extract the `### status` section body up to the next `###` header."""
    marker = "### `status`"
    idx = text.find(marker)
    if idx == -1:
        return ""
    rest = text[idx + len(marker):]
    nxt = rest.find("\n### ")
    return rest if nxt == -1 else rest[:nxt]


def _fenced_command_lines(section: str) -> list[str]:
    """Return the stripped lines inside ``` fenced code blocks of the section.

    These are the actual commands the dispatcher would run. The prohibition
    prose mentions `ls .rabbit-auto-evolve-*` in backticks OUTSIDE code
    fences, so scanning only fenced blocks distinguishes a real bare-ls
    command from prose that forbids it.
    """
    lines: list[str] = []
    in_fence = False
    for line in section.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            lines.append(line.strip())
    return lines


for label, skill_path in (("source", SOURCE_SKILL), ("deployed", DEPLOYED_SKILL)):
    if not skill_path.is_file():
        fail_t(f"skill-{label}/exists", f"SKILL.md not found: {skill_path}")
        continue
    text = skill_path.read_text()
    section = _status_section(text)
    if not section:
        fail_t(f"skill-{label}/section", "could not locate `### status` section")
        continue
    if INVOCATION not in section:
        fail_t(
            f"skill-{label}/invokes",
            f"status section does not invoke status-report.py ({INVOCATION!r})",
        )
    else:
        ok(f"skill-{label}/invokes", "status section invokes status-report.py")
    cmd_lines = _fenced_command_lines(section)
    bad_cmds = [
        ln
        for ln in cmd_lines
        if ln.startswith("ls .rabbit-auto-evolve-")
        or ln.startswith("cat .rabbit/auto-evolve-state.json")
    ]
    if bad_cmds:
        fail_t(
            f"skill-{label}/no-bare-cmd",
            f"status section runs an ad-hoc bash command: {bad_cmds}",
        )
    else:
        ok(
            f"skill-{label}/no-bare-cmd",
            "status section runs no bare ls/cat pipeline (only the script)",
        )

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
