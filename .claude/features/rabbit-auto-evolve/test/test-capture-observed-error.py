#!/usr/bin/env python3
"""test-capture-observed-error.py — rabbit-auto-evolve Inv 67 (issue #1091).

Unit-tests the deterministic self-observed-error capture script
`scripts/capture-observed-error.py`. The script owns BOTH halves of the
deterministic mechanics so the orchestrator only performs the irreducible
Agent() dispatch:

  1. `analysis-prompt` — given a structured error record on stdin, assemble
     the ISOLATED analysis-subagent dispatch prompt (context isolation: the
     deep root-cause analysis runs in its own subagent, NOT inline in the
     dispatcher's accumulating context).
  2. `file-args` — given the analysis subagent's structured verdict on stdin,
     assemble the deterministic `file-item.py` argv (feature / priority /
     type / title / description / provenance) for the well-formed issue a
     later tick handles.

Recursion guard: an error record whose phase marks it as having occurred
DURING error-capture itself MUST NOT re-trigger capture (capture-of-capture
must not recurse infinitely). Both subcommands refuse such a record.

Routine-vs-abort: a routine captured error returns `capture` (file an issue,
keep going) — it is NOT the hard safety-abort path; the script never emits an
abort signal.

Non-interactive. Exits non-zero on first failure.
"""

import json
import subprocess
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "capture-observed-error.py"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run(args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


# A representative observed-error record: a non-zero script exit mid-tick.
ERROR_RECORD = {
    "command": "python3 .claude/features/rabbit-auto-evolve/scripts/merge-prs.py 42",
    "exit_code": 1,
    "stderr_excerpt": "gh-merge-failed: required status check pending",
    "stdout_excerpt": "",
    "phase": "merge",
    "context": "tick 2026-06-06T12:00:00Z, PR 42",
}

# --- 1. --help smoke ---
r = run(["--help"])
if r.returncode == 0 and "usage" in (r.stdout + r.stderr).lower():
    ok("--help exits 0 with usage text")
else:
    fail(f"--help did not exit 0 with usage; rc={r.returncode}")

# --- 2. analysis-prompt assembles an ISOLATED-subagent dispatch prompt ---
r = run(["analysis-prompt"], stdin=json.dumps(ERROR_RECORD))
if r.returncode != 0:
    fail(f"analysis-prompt non-zero exit: {r.returncode}; {r.stderr}")
else:
    prompt = r.stdout
    lo = prompt.lower()
    # The prompt must embed the concrete observed-error facts so the isolated
    # subagent can do bounded root-cause analysis WITHOUT re-deriving them.
    needed = [
        ERROR_RECORD["command"],
        ERROR_RECORD["stderr_excerpt"],
        str(ERROR_RECORD["exit_code"]),
        ERROR_RECORD["phase"],
    ]
    missing = [n for n in needed if n not in prompt]
    if missing:
        fail(f"analysis-prompt omits error facts: {missing!r}")
    else:
        ok("analysis-prompt embeds the observed-error facts")
    # It must instruct a BOUNDED root-cause analysis returning a STRUCTURED
    # verdict (machine-first handoff), and name the isolation rationale.
    if "root" in lo and "cause" in lo and ("json" in lo or "structured" in lo):
        ok("analysis-prompt asks for a bounded structured root-cause verdict")
    else:
        fail("analysis-prompt missing bounded structured root-cause ask")
    # It must NOT dispatch a TDD subagent / open a PR — analysis only.
    if "do not" in lo or "must not" in lo:
        ok("analysis-prompt constrains the subagent (no fix, analysis only)")
    else:
        fail("analysis-prompt does not constrain to analysis-only")

# --- 3. file-args assembles the deterministic file-item.py argv ---
VERDICT = {
    "feature": "rabbit-auto-evolve",
    "priority": "high",
    "issue_type": "bug",
    "title": "merge-prs.py fails on pending required status check",
    "summary": "The merge phase exits non-zero when a required status check "
               "is still pending; the loop should defer rather than fail.",
}
combined = {"error": ERROR_RECORD, "verdict": VERDICT}
r = run(["file-args"], stdin=json.dumps(combined))
if r.returncode != 0:
    fail(f"file-args non-zero exit: {r.returncode}; {r.stderr}")
else:
    try:
        argv = json.loads(r.stdout)
    except ValueError as e:
        argv = None
        fail(f"file-args did not emit a JSON array: {e}")
    if argv is not None:
        if not isinstance(argv, list):
            fail("file-args output is not a JSON array")
        else:
            joined = " ".join(argv)
            # Must invoke rabbit-issue file-item.py (contract INVOKE).
            if "file-item.py" in joined:
                ok("file-args targets rabbit-issue file-item.py")
            else:
                fail("file-args does not target file-item.py")

            def flag_val(flag):
                if flag in argv:
                    i = argv.index(flag)
                    if i + 1 < len(argv):
                        return argv[i + 1]
                return None

            checks = {
                "--feature": VERDICT["feature"],
                "--priority": VERDICT["priority"],
                "--type": VERDICT["issue_type"],
            }
            for flag, want in checks.items():
                got = flag_val(flag)
                if got == want:
                    ok(f"file-args carries {flag} {want}")
                else:
                    fail(f"file-args {flag}={got!r}, want {want!r}")
            # Title must be present and carry the verdict title.
            if flag_val("--title") == VERDICT["title"]:
                ok("file-args carries the verdict --title")
            else:
                fail(f"file-args --title wrong: {flag_val('--title')!r}")
            # Description must be present and reference the observed command +
            # exit code so the filed issue is self-contained for a later tick.
            desc = flag_val("--description") or ""
            if (ERROR_RECORD["command"] in desc
                    and str(ERROR_RECORD["exit_code"]) in desc):
                ok("file-args --description embeds the observed command + exit")
            else:
                fail("file-args --description missing command/exit facts")
            # Provenance: autonomous-evolve (the loop filed it, not a human).
            if flag_val("--filed-by") == "autonomous-evolve":
                ok("file-args stamps --filed-by autonomous-evolve")
            else:
                fail("file-args missing --filed-by autonomous-evolve")

# --- 4. recursion guard: a capture-phase error refuses both subcommands ---
RECURSIVE = dict(ERROR_RECORD)
RECURSIVE["phase"] = "error-capture"
for sub in ("analysis-prompt", "file-args"):
    payload = RECURSIVE if sub == "analysis-prompt" else {
        "error": RECURSIVE, "verdict": VERDICT}
    r = run([sub], stdin=json.dumps(payload))
    if r.returncode != 0:
        ok(f"{sub} refuses a capture-of-capture record (rc={r.returncode})")
    else:
        fail(f"{sub} did not refuse a capture-of-capture record")

# --- 5. routine-vs-abort: the script never emits an abort signal ---
# A routine captured error produces a file-item argv; it does not write any
# abort marker and emits no abort verdict on stdout.
r = run(["file-args"], stdin=json.dumps(combined))
combined_out = (r.stdout + r.stderr).lower()
if "abort" not in combined_out:
    ok("capture is routine — no abort signal emitted")
else:
    fail("capture emitted an abort signal (should be routine, not a halt)")

# --- 6. priority/type fall back deterministically when verdict omits them ---
THIN_VERDICT = {
    "feature": "rabbit-auto-evolve",
    "title": "anomaly observed",
    "summary": "something looked off",
}
r = run(["file-args"], stdin=json.dumps({"error": ERROR_RECORD,
                                         "verdict": THIN_VERDICT}))
if r.returncode == 0:
    argv = json.loads(r.stdout)

    def fv(flag):
        return argv[argv.index(flag) + 1] if flag in argv else None
    # Default type when omitted must be a valid file-item type.
    if fv("--type") in ("bug", "enhancement"):
        ok(f"file-args defaults --type to {fv('--type')!r} when omitted")
    else:
        fail(f"file-args default --type invalid: {fv('--type')!r}")
    # Default priority when omitted must be a valid file-item priority.
    if fv("--priority") in ("low", "medium", "high", "critical"):
        ok(f"file-args defaults --priority to {fv('--priority')!r}")
    else:
        fail(f"file-args default --priority invalid: {fv('--priority')!r}")
else:
    fail(f"file-args failed on a thin verdict: {r.stderr}")

# --- 7. malformed stdin → non-zero, no crash ---
r = run(["file-args"], stdin="not json")
if r.returncode != 0:
    ok("file-args exits non-zero on malformed stdin")
else:
    fail("file-args accepted malformed stdin")

sys.exit(FAIL)
