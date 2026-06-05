#!/usr/bin/env python3
"""check-script-backed.py — deterministic scan for orchestration steps that
violate the spec-rules §4 Script-Backed Orchestration standard.

Housekeeping enforces §4 as a SCRIPT-tier verification DIMENSION: the check
embodies the same `script > CLI > spec > prompt` tier it enforces. This script
walks a target feature's authored bodies and flags every orchestration step
that is NOT script-backed.

A fenced bash block in a `skills/*/SKILL.md`, `agents/*.md`, or
`commands/*.md` body is FLAGged when it:

  - carries a RUNTIME PLACEHOLDER (e.g. `<feature-name>`, `<branch-name>`)
    the model assembles at invocation time — that is prompt-tier, not
    script-tier (reason: runtime-placeholder); OR
  - performs MODE-AWARE BRANCHING (shell `if` / `elif` / `case`) — branching
    logic belongs in a companion script the body invokes
    (reason: mode-aware-branching); OR
  - COMPUTES A VALUE via command substitution `$(...)` / backticks or shell
    arithmetic `$((...))` that the body then assembles — the computation
    belongs in a companion script (reason: computed-value).

EXCEPTION (§4 read-only-informational): a block that does none of the above —
e.g. a read-only informational command `git log --oneline -5`, or a trivial
one-liner that simply invokes a companion `scripts/*.py` — is NOT flagged.

Subcommand:

  scan <feature-dir>
    Walk <feature-dir>/skills/*/SKILL.md, <feature-dir>/agents/*.md, and
    <feature-dir>/commands/*.md, classify each fenced bash block, and print a
    JSON object:
      {
        "findings": [
          {"file": "<abs path>", "line": <1-based block start>,
           "reason": "runtime-placeholder|computed-value|mode-aware-branching",
           "snippet": "<first offending line, trimmed>"}
        ],
        "count": <len(findings)>
      }
    A block matching more than one reason is reported once, by the
    first-listed matching reason (placeholder > branching > computed). The
    count/findings are the report; the caller's verify-or-flag disposition
    acts on them (the script reports, it does not gate).

Exit:
  0 scan ran (whether or not findings were emitted)
  2 invocation error (missing subcommand, missing/bad feature-dir)

Version: 0.3.0
Owner: rabbit-workflow team
Deprecation criterion: when script-backed-orchestration linting is provided
    natively by the rabbit CLI as a housekeeping subcommand.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

# A runtime placeholder: an angle-bracketed token the model fills at
# invocation time, e.g. <feature-name>, <branch-name>, <name>. Restricted to
# lowercase/digit/hyphen/underscore inside the brackets so it does not match
# shell redirection (`2>&1`, `<<EOF`) or process-substitution `<(...)`.
_PLACEHOLDER = re.compile(r"<[a-z][a-z0-9._-]*>")

# Mode-aware branching: a shell conditional construct.
_BRANCH = re.compile(r"(?m)^\s*(?:if|elif|case)\b")

# Computed value: command substitution `$(...)`, backticks, or arithmetic
# `$((...))`. Arithmetic is matched first/independently; plain `$(...)` also
# covers `$((...))` textually, which is fine — both mean "compute in-band".
_COMMAND_SUB = re.compile(r"\$\(")
_BACKTICK = re.compile(r"`[^`]+`")

# A fenced bash block: ```bash ... ``` (also ```sh / ```shell).
_FENCE = re.compile(
    r"(?ms)^```(?:bash|sh|shell)[^\n]*\n(.*?)^```",
)


def _first_matching_line(block: str, pattern: re.Pattern) -> str:
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if pattern.search(line):
            return line
    # Fall back to a block-level match (e.g. a multi-line `case`): return the
    # first non-comment, non-blank line.
    for raw in block.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            return line
    return block.strip().splitlines()[0] if block.strip() else ""


def _classify(block: str):
    """Return (reason, snippet) for the first matching reason, or None."""
    # Placeholder takes precedence: a placeholder makes the step prompt-tier
    # regardless of whether it also invokes a script.
    if _PLACEHOLDER.search(block):
        return "runtime-placeholder", _first_matching_line(block, _PLACEHOLDER)
    if _BRANCH.search(block):
        return "mode-aware-branching", _first_matching_line(block, _BRANCH)
    if _COMMAND_SUB.search(block) or _BACKTICK.search(block):
        pat = _COMMAND_SUB if _COMMAND_SUB.search(block) else _BACKTICK
        return "computed-value", _first_matching_line(block, pat)
    return None


def _scan_file(path: str):
    findings = []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for m in _FENCE.finditer(text):
        block = m.group(1)
        verdict = _classify(block)
        if verdict is None:
            continue
        reason, snippet = verdict
        # 1-based line of the opening fence.
        line = text.count("\n", 0, m.start()) + 1
        findings.append({
            "file": os.path.abspath(path),
            "line": line,
            "reason": reason,
            "snippet": snippet,
        })
    return findings


def _target_files(feature_dir: str):
    files = []
    files.extend(sorted(glob.glob(
        os.path.join(feature_dir, "skills", "*", "SKILL.md"))))
    files.extend(sorted(glob.glob(
        os.path.join(feature_dir, "agents", "*.md"))))
    files.extend(sorted(glob.glob(
        os.path.join(feature_dir, "commands", "*.md"))))
    return files


def cmd_scan(args):
    if len(args) != 1:
        sys.stderr.write("usage: check-script-backed.py scan <feature-dir>\n")
        return 2
    feature_dir = args[0]
    if not os.path.isdir(feature_dir):
        sys.stderr.write(f"ERROR: not a directory: {feature_dir}\n")
        return 2
    findings = []
    for path in _target_files(feature_dir):
        findings.extend(_scan_file(path))
    print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
    return 0


def main(argv):
    if not argv:
        sys.stderr.write(
            "usage: check-script-backed.py scan <feature-dir>\n"
        )
        return 2
    sub = argv[0]
    rest = argv[1:]
    if sub == "scan":
        return cmd_scan(rest)
    sys.stderr.write(f"ERROR: unknown subcommand {sub!r}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
