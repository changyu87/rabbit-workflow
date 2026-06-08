#!/usr/bin/env python3
"""capture-observed-error.py — deterministic self-observed-error capture.

Per rabbit-auto-evolve spec.md Inv 67 (issue #1091). Today the orchestrator
files issues only REACTIVELY (a subagent's `discovered_issues`, decomposition
sub-issues); it has no mandate to capture a defect it observes ITSELF. A
self-observed error mid-tick — a non-zero bash/script exit, unexpected
stderr/output, or an anomaly — was either aborted-and-halted or silently
dropped. This script gives the orchestrator a BOUNDED capture capability that
owns BOTH deterministic halves of the mechanism so the dispatcher performs
only the irreducible Agent() dispatch:

  analysis-prompt
      Reads a structured error record (JSON on stdin) and emits the dispatch
      prompt for an ISOLATED analysis subagent on stdout. The analysis runs in
      its OWN subagent context, NOT inline in the dispatcher's accumulating
      context — important on the croncreate session-reuse path where the
      dispatcher's context accumulates across ticks; a deep root-cause
      analysis would otherwise bloat/pollute it. The subagent is told to do a
      bounded root-cause analysis and return a STRUCTURED verdict.

  file-args
      Reads {"error": <record>, "verdict": <analysis verdict>} (JSON on stdin)
      and emits, on stdout, the deterministic `file-item.py` argv (a JSON
      array) the orchestrator runs to file a well-formed issue for a LATER
      tick to handle, with the right feature: + priority: labels and
      `--filed-by autonomous-evolve` provenance.

Recursion guard: a record whose `phase` is `error-capture` occurred DURING
error capture itself; both subcommands REFUSE it so capture-of-capture cannot
recurse infinitely.

Routine, not abort: a captured error is ROUTINE — the loop files an issue and
keeps going. This is NOT the hard safety-abort path (`mark-aborted.py`), which
is reserved for hard blockers. This script never writes an abort marker and
never emits an abort signal.

The error record schema (all fields optional except `command`):
  {
    "command": "<the observed command>",
    "exit_code": <int>,
    "stderr_excerpt": "<bounded stderr>",
    "stdout_excerpt": "<bounded stdout>",
    "phase": "<tick phase / context tag>",
    "context": "<free-form context, e.g. tick id + target>"
  }

Exit code: 0 on success; non-zero on malformed stdin, a recursion-guard
refusal, or a missing required field.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import sys

# The phase tag that marks an error observed DURING error capture itself. A
# record carrying it MUST NOT re-trigger capture (recursion guard).
CAPTURE_PHASE = "error-capture"

VALID_TYPES = ("bug", "enhancement")
VALID_PRIORITIES = ("low", "medium", "high", "critical")
DEFAULT_TYPE = "bug"
DEFAULT_PRIORITY = "medium"

FILE_ITEM = ".claude/features/rabbit-issue/scripts/file-item.py"


def _read_stdin_json():
    raw = sys.stdin.read()
    return json.loads(raw)


def _is_recursive(record):
    return str(record.get("phase", "")).strip().lower() == CAPTURE_PHASE


def _excerpt(value, limit=800):
    s = "" if value is None else str(value)
    if len(s) > limit:
        return s[:limit] + " …[truncated]"
    return s


def build_analysis_prompt(record):
    """Assemble the isolated analysis-subagent dispatch prompt."""
    command = record.get("command", "")
    exit_code = record.get("exit_code", "")
    stderr = _excerpt(record.get("stderr_excerpt", ""))
    stdout = _excerpt(record.get("stdout_excerpt", ""))
    phase = record.get("phase", "")
    context = record.get("context", "")

    return f"""\
You are an ISOLATED error-analysis subagent dispatched by the rabbit-auto-evolve
orchestrator (a main-session, level-1 Agent dispatch, exactly like the Phase-6
TDD dispatch). You run in your OWN context so the deep analysis below does NOT
bloat or pollute the dispatcher's accumulating context (the dispatcher reuses
its session across ticks on the croncreate path).

The orchestrator observed the following error mid-tick:

  command:       {command}
  exit_code:     {exit_code}
  phase:         {phase}
  context:       {context}
  stderr:        {stderr}
  stdout:        {stdout}

Do a BOUNDED root-cause analysis. Inspect ONLY what you need to explain this
specific error — do NOT fix it, do NOT open a PR, do NOT dispatch any further
subagent. Analysis ONLY.

Return a STRUCTURED verdict as a single JSON object on your final line:

  {{
    "feature": "<the rabbit feature this error belongs to, e.g. rabbit-auto-evolve>",
    "priority": "low|medium|high|critical",
    "issue_type": "bug|enhancement",
    "title": "<short imperative issue title>",
    "summary": "<one-paragraph root-cause summary for a later tick to act on>"
  }}

The orchestrator feeds your verdict to capture-observed-error.py file-args to
file a well-formed issue for a LATER tick. You MUST NOT file the issue yourself.
"""


def build_file_args(record, verdict):
    """Assemble the deterministic file-item.py argv (a list)."""
    feature = verdict.get("feature")
    if not feature:
        raise ValueError("verdict missing required 'feature'")

    issue_type = verdict.get("issue_type")
    if issue_type not in VALID_TYPES:
        issue_type = DEFAULT_TYPE

    priority = verdict.get("priority")
    if priority not in VALID_PRIORITIES:
        priority = DEFAULT_PRIORITY

    title = verdict.get("title") or "self-observed loop error"

    command = record.get("command", "")
    exit_code = record.get("exit_code", "")
    phase = record.get("phase", "")
    context = record.get("context", "")
    stderr = _excerpt(record.get("stderr_excerpt", ""))
    summary = verdict.get("summary", "")

    description = (
        f"{summary}\n\n"
        f"Self-observed by the auto-evolve loop (Inv 67).\n\n"
        f"- observed command: {command}\n"
        f"- exit code: {exit_code}\n"
        f"- phase: {phase}\n"
        f"- context: {context}\n"
        f"- stderr excerpt: {stderr}\n"
    )

    return [
        "python3", FILE_ITEM,
        "--type", issue_type,
        "--feature", feature,
        "--title", title,
        "--priority", priority,
        "--description", description,
        "--filed-by", "autonomous-evolve",
    ]


def cmd_analysis_prompt(_args):
    try:
        record = _read_stdin_json()
    except ValueError as e:
        sys.stderr.write(f"capture-observed-error: bad stdin JSON: {e}\n")
        return 1
    if not isinstance(record, dict):
        sys.stderr.write("capture-observed-error: error record must be an object\n")
        return 1
    if _is_recursive(record):
        sys.stderr.write(
            "capture-observed-error: refusing capture-of-capture "
            f"(phase={CAPTURE_PHASE!r}); the recursion guard prevents an "
            "error WHILE capturing an error from re-triggering capture\n"
        )
        return 1
    if not record.get("command"):
        sys.stderr.write("capture-observed-error: error record missing 'command'\n")
        return 1
    sys.stdout.write(build_analysis_prompt(record))
    return 0


def cmd_file_args(_args):
    try:
        payload = _read_stdin_json()
    except ValueError as e:
        sys.stderr.write(f"capture-observed-error: bad stdin JSON: {e}\n")
        return 1
    if not isinstance(payload, dict):
        sys.stderr.write("capture-observed-error: file-args input must be an object\n")
        return 1
    record = payload.get("error")
    verdict = payload.get("verdict")
    if not isinstance(record, dict) or not isinstance(verdict, dict):
        sys.stderr.write(
            "capture-observed-error: file-args needs {\"error\": {...}, "
            "\"verdict\": {...}}\n"
        )
        return 1
    if _is_recursive(record):
        sys.stderr.write(
            "capture-observed-error: refusing capture-of-capture "
            f"(phase={CAPTURE_PHASE!r}); the recursion guard prevents an "
            "error WHILE capturing an error from re-triggering capture\n"
        )
        return 1
    try:
        argv = build_file_args(record, verdict)
    except ValueError as e:
        sys.stderr.write(f"capture-observed-error: {e}\n")
        return 1
    json.dump(argv, sys.stdout)
    sys.stdout.write("\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic self-observed-error capture (Inv 67 / "
                    "#1091): assemble the ISOLATED analysis-subagent dispatch "
                    "prompt and the file-item.py argv so the orchestrator only "
                    "performs the irreducible Agent() dispatch."
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser(
        "analysis-prompt",
        help="emit the isolated analysis-subagent dispatch prompt "
             "(reads an error record JSON on stdin)",
    )
    sub.add_parser(
        "file-args",
        help="emit the deterministic file-item.py argv as a JSON array "
             "(reads {error, verdict} JSON on stdin)",
    )
    args = parser.parse_args()
    if args.subcommand == "analysis-prompt":
        return cmd_analysis_prompt(args)
    if args.subcommand == "file-args":
        return cmd_file_args(args)
    parser.error("unknown subcommand")


if __name__ == "__main__":
    sys.exit(main())
