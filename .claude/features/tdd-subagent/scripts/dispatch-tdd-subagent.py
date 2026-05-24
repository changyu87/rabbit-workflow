#!/usr/bin/env python3
# dispatch-tdd-subagent.py — assembles the prompt for a per-feature TDD subagent.
#
# Usage:
#   dispatch-tdd-subagent.py \
#     --scope <feature-name> \
#     --spec <spec-path> \
#     [--impl-suggestion <path>] \
#     [--linked-item <dir>] \
#     [--item-type bug|backlog] \
#     [--linked-items <feature>:<type>:<id>[,<feature>:<type>:<id>...]] \
#     [--human-approval-gate true|false] \
#     [--code-review-full-loop] \
#     [--max-iterations N]
#
# --linked-items accepts a comma-separated list of `<feature>:<type>:<id>`
# triples identifying secondary bugs/backlog items resolved by the same TDD
# cycle. Each triple must have exactly two colons, non-empty fields, and a
# type in {bug, backlog}. Malformed triples cause a non-zero exit BEFORE the
# prompt is emitted. After test-green, the dispatched subagent closes the
# primary --linked-item (if any) plus every secondary item via
# `item-status.py set --feature <f> --type <t> --id <id> --status close
# --fix-commits <impl-sha>`, and lists all closed items in HANDOFF.closed_items.
#
# Output: assembled prompt to stdout. Caller: Agent(model: opus, prompt: stdout).
# Version: 3.0.0
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when TDD cycle is natively supported by rabbit CLI.

import argparse
import os
import subprocess
import sys
from pathlib import Path as _Path

# Pull in the rabbit_print renderer from the contract feature. The
# renderer is the sole authorized emission path for the preamble bypass
# note (Inv 23, Inv 24); inline ANSI/brand strings here are forbidden.
_CONTRACT_SCRIPTS = _Path(__file__).resolve().parents[2] / "contract" / "scripts"
if str(_CONTRACT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CONTRACT_SCRIPTS))
from rabbit_print import rabbit_print  # noqa: E402

# Canonical preamble text. Grep-stable: tests assert this exact body.
_BYPASS_NOTE_TEXT = (
    "NOTE: human-approval bypass marker is active "
    "(.rabbit-human-approval-bypass). Step 4 HUMAN-APPROVAL will be "
    "skipped for this dispatch. Revoke via "
    "`/rabbit-config human-approval true`."
)


def _repo_root(script_dir):
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _read_file(path, default="(not found)"):
    if path and os.path.isfile(path):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            pass
    return default


def _policy_block(repo_root):
    py = os.path.join(repo_root, ".claude", "features", "contract", "scripts", "policy-block.py")
    if not os.path.isfile(py):
        return ""
    try:
        res = subprocess.run([sys.executable, py], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return res.stdout.rstrip("\n")
    except Exception:
        pass
    return ""


def _find_feature(repo_root, feature_name):
    find_py = os.path.join(repo_root, ".claude", "features", "contract", "scripts", "find-feature.py")
    try:
        res = subprocess.run(
            [sys.executable, find_py, repo_root, "lookup", feature_name],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def main(argv):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = _repo_root(script_dir)

    parser = argparse.ArgumentParser(
        prog="dispatch-tdd-subagent.py",
        description=("Assemble a per-feature TDD subagent prompt that runs the "
                     "9-step TDD cycle (spec-update -> test-red -> impl -> "
                     "test-green) for ONE feature. Prompt is written to stdout."),
    )
    parser.add_argument("--scope", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--impl-suggestion", default=None)
    parser.add_argument("--linked-item", default=None)
    parser.add_argument("--item-type", default=None, choices=["bug", "backlog"])
    parser.add_argument("--linked-items", default=None,
                        help="Comma-separated <feature>:<type>:<id> triples for secondary "
                             "items closed by the same impl commit (type in {bug, backlog}). "
                             "Malformed triples cause non-zero exit before prompt emit.")
    parser.add_argument(
        "--human-approval-gate",
        choices=["true", "false"],
        default="true",
        help="'true' (default) requires explicit user approval in the subagent's "
             "HUMAN-APPROVAL step; 'false' skips that step.",
    )
    parser.add_argument("--code-review-full-loop", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=3)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 0 on --help (already printed full help); pass through.
        # Any other code (typically 2 for arg errors) becomes our usage hint.
        if exc.code == 0:
            return 0
        sys.stderr.write(
            "ERROR: usage: dispatch-tdd-subagent.py --scope <feature> --spec <path> "
            "[--impl-suggestion <path>] [--linked-item <dir>] [--item-type bug|backlog] "
            "[--linked-items <feature>:<type>:<id>[,...]] "
            "[--human-approval-gate true|false] [--code-review-full-loop] "
            "[--max-iterations N]\n"
        )
        return 2

    if args.linked_item and not args.item_type:
        sys.stderr.write("ERROR: --linked-item requires --item-type\n")
        return 2
    if args.item_type and not args.linked_item:
        sys.stderr.write("ERROR: --item-type requires --linked-item\n")
        return 2
    if args.max_iterations < 1:
        sys.stderr.write("ERROR: --max-iterations must be >= 1\n")
        return 2
    # --spec path must be a real file. Without this guard the embedded SPEC
    # block in the prompt silently becomes "(not found)" and the subagent has
    # nothing to implement against. Fail fast at invocation time.
    if not os.path.isfile(args.spec):
        sys.stderr.write(
            f"ERROR: --spec file does not exist: {args.spec}\n"
        )
        return 2

    # Parse and validate --linked-items into a list of (feature, type, id) tuples.
    # Each malformed entry causes exit(2) BEFORE any prompt is emitted on stdout.
    secondary_items = []
    if args.linked_items:
        allowed_types = {"bug", "backlog"}
        for raw in args.linked_items.split(","):
            entry = raw.strip()
            if not entry:
                sys.stderr.write(
                    "ERROR: --linked-items contains an empty entry "
                    "(check for stray commas)\n"
                )
                return 2
            parts = entry.split(":")
            if len(parts) != 3:
                sys.stderr.write(
                    f"ERROR: --linked-items entry '{entry}' is malformed: "
                    f"expected exactly two colons in '<feature>:<type>:<id>'\n"
                )
                return 2
            feat, typ, iid = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not feat or not typ or not iid:
                sys.stderr.write(
                    f"ERROR: --linked-items entry '{entry}' has an empty field; "
                    f"all of <feature>, <type>, <id> must be non-empty\n"
                )
                return 2
            if typ not in allowed_types:
                sys.stderr.write(
                    f"ERROR: --linked-items entry '{entry}' has invalid type '{typ}'; "
                    f"allowed types: bug, backlog\n"
                )
                return 2
            secondary_items.append((feat, typ, iid))

    feature_name = args.scope
    feature_path = _find_feature(repo_root, feature_name)
    if not feature_path:
        sys.stderr.write(f"ERROR: feature '{feature_name}' not found\n")
        # Inv: invocation errors return 2 (see contract.md exit codes).
        # A missing feature is a caller-side mistake, not a runtime failure.
        return 2

    feature_dir = os.path.join(repo_root, feature_path)
    tdd_step_py = os.path.join(repo_root, ".claude", "features", "tdd-state-machine", "scripts", "tdd-step.py")

    spec_content = _read_file(args.spec)
    impl_suggestion_block = ""
    if args.impl_suggestion:
        raw = _read_file(args.impl_suggestion)
        if raw != "(not found)":
            impl_suggestion_block = f"\n## Implementation Suggestion\n\n```json\n{raw}\n```\n"

    policy_block = _policy_block(repo_root)
    linked_item_value = args.linked_item or "null"
    item_type_value = args.item_type or "null"

    # Emit the bypass-marker preamble note when the human-approval
    # bypass marker exists at the repo root (Inv 23). The note appears
    # on every dispatch while the marker is present; it does not
    # consume the marker. rabbit_print is the sole emission path
    # (Inv 24) — no inline ANSI/brand strings in this file.
    bypass_marker_path = os.path.join(repo_root, ".rabbit-human-approval-bypass")
    if os.path.isfile(bypass_marker_path):
        bypass_preamble_note = "\n" + rabbit_print(
            _BYPASS_NOTE_TEXT, "📢", "yellow") + "\n"
    else:
        bypass_preamble_note = ""

    item_status_py = os.path.join(
        repo_root, ".claude", "features", "rabbit-file", "scripts", "item-status.py"
    )

    # Build close-call block for STEP 9 UNLOCK (Inv 19/20: all close
    # calls route through rabbit-file's `item-status.py set ...`). One
    # loop, one template — primary and secondary differ only by comment,
    # reason, and the HANDOFF label string. Baseline prompt (no items)
    # is unchanged.
    items = []
    if args.linked_item and args.item_type:
        parts = [p for p in args.linked_item.replace("\\", "/").split("/") if p]
        feat = parts[-3] if len(parts) >= 3 else "unknown"
        iid = parts[-1] if parts else "unknown"
        items.append({
            "feat": feat, "typ": args.item_type, "iid": iid,
            "comment": "Primary linked item (closed by impl commit):",
            "reason": "TDD cycle complete",
            "handoff_label": f"{args.linked_item} (primary, type={args.item_type})",
        })
    for feat, typ, iid in secondary_items:
        items.append({
            "feat": feat, "typ": typ, "iid": iid,
            "comment": "Secondary linked item (resolved by same impl commit):",
            "reason": "TDD cycle complete (secondary item resolved by same commit)",
            "handoff_label": f"{feat}:{typ}:{iid} (secondary)",
        })

    def _render_close(it):
        return (
            f"  # {it['comment']}\n"
            f"  python3 {item_status_py} set \\\n"
            f"    --feature {it['feat']} --type {it['typ']} --id {it['iid']} \\\n"
            f"    --status close \\\n"
            f"    --reason '{it['reason']}' \\\n"
            f"    --fix-commits $IMPL_SHA\n"
        )

    if items:
        close_calls_block = (
            "\nAfter the test-green transition is committed, capture the impl commit SHA\n"
            "and close the linked item(s):\n\n"
            "  IMPL_SHA=$(git rev-parse HEAD)\n\n"
            + "\n".join(_render_close(it) for it in items)
        )
        handoff_closed_items_block = (
            "\n  closed_items:\n"
            + "\n".join(f"    - {it['handoff_label']}" for it in items)
        )
        # JSON HANDOFF closed_items reflects the same closures (Inv 21,
        # Inv 22 — the JSON block is the machine-first source of truth;
        # closed items appear here, not only in the YAML block above).
        handoff_closed_items_json = (
            "[\n    "
            + ",\n    ".join(f'"{it["handoff_label"]}"' for it in items)
            + "\n  ]"
        )
    else:
        close_calls_block = ""
        handoff_closed_items_block = ""
        handoff_closed_items_json = "[]"

    # All step banners use the uniform ═════ banner format. Both gated and
    # bypassed forms use the same heading style for visual consistency.
    if args.human_approval_gate == "false":
        human_approval_section = (
            "\n"
            "════════════════════════════════════════════════════════════════════════\n"
            "STEP 2 — HUMAN-APPROVAL\n"
            "════════════════════════════════════════════════════════════════════════\n"
            "\n"
            "Skipped (--human-approval-gate false).\n"
        )
    else:
        human_approval_section = (
            "\n"
            "════════════════════════════════════════════════════════════════════════\n"
            "STEP 2 — HUMAN-APPROVAL\n"
            "════════════════════════════════════════════════════════════════════════\n"
            "\n"
            "Invoke `Skill(\"superpowers:writing-plans\")` to produce an implementation summary with:\n"
            "- Key implementation points (bullet list)\n"
            "- Affected files (explicit paths)\n"
            "\n"
            "Present this summary to the user and wait for explicit approval before Step 3 (LOCK).\n"
            "If the user requests changes, update and re-present. Do NOT proceed without approval.\n"
        )

    if args.code_review_full_loop:
        code_review_loop_note = (
            "--code-review-full-loop is active: after any code changes from CODE-REVIEW, "
            "loop back to Step 4 (TEST-WRITE) and repeat until CODE-REVIEW produces no further changes."
        )
    else:
        code_review_loop_note = (
            "Default mode: use judgment — loop back to Step 4 (TEST-WRITE) only if "
            "CODE-REVIEW changed functional code or tests. HUMAN-APPROVAL (Step 2) does NOT re-run on loop-back."
        )

    prompt = f"""{policy_block}
{bypass_preamble_note}
════════════════════════════════════════════════════════════════════════
TDD SUBAGENT — SCOPE: {feature_name}
════════════════════════════════════════════════════════════════════════

You are a TDD subagent. Execute the 9 named steps below IN ORDER for feature: {feature_name}
Do NOT skip steps. Do NOT dispatch nested subagents. All work is done inline.

════════════════════════════════════════════════════════════════════════
SPEC
════════════════════════════════════════════════════════════════════════

{spec_content}
{impl_suggestion_block}
════════════════════════════════════════════════════════════════════════
E2E TEST RULE (non-negotiable)
════════════════════════════════════════════════════════════════════════

Every behaviour described in the spec MUST have a corresponding end-to-end test.
Unit tests alone are insufficient. If a spec behaviour has no e2e test, add one in TEST-WRITE.
This rule applies to ALL TDD cycles without exception.

════════════════════════════════════════════════════════════════════════
SCOPE BOUNDARY — RED FLAG (non-negotiable)
════════════════════════════════════════════════════════════════════════

Your declared scope is feature: {feature_name}. The only scope marker
you may create is .rabbit-scope-active-{feature_name} (at LOCK).

You MUST NOT create any .rabbit-scope-active-<X> marker where X != {feature_name},
even temporarily. Creating an out-of-scope scope marker is a CONSTITUTION
VIOLATION. Never do this.

If implementation work requires writing to a file inside another feature's
directory (anywhere under .claude/features/<X>/ where X != {feature_name}):

1. STOP. Do not write the file. Do not create another marker.
2. Emit HANDOFF with:
     HANDOFF:
       feature: {feature_name}
       tdd_state: blocked
       test_result: not_run
       cross_feature_dependency: <X>
       unwritten_paths:
         - <full path 1>
         - <full path 2>
       notes: <one sentence describing the cross-feature dependency>
3. Do not call tdd-step.py for any further transitions.
4. Do not run the test suite.

The dispatcher will read the HANDOFF, surface the cross-feature dependency to
the user, and split the work into a separate cycle for <X> if the user approves.

════════════════════════════════════════════════════════════════════════
SKILL.md ROUTING — RED FLAG (non-negotiable)
════════════════════════════════════════════════════════════════════════

If any file your implementation must edit has the basename `SKILL.md`
(e.g., .claude/features/<X>/skills/<Y>/SKILL.md or
.claude/skills/<Y>/SKILL.md), you MUST invoke
Skill("skill-creator:skill-creator") and let it drive the edit.

Using Write or Edit directly on a SKILL.md is a CONSTITUTION VIOLATION:
it bypasses skill-creator's eval loop and description optimization,
and produces SKILL.md files that drift from the skill-authoring contract.

This rule applies at STEP 6 (IMPLEMENT). It has no exceptions.

════════════════════════════════════════════════════════════════════════
STEP 1 — SPEC-READ
════════════════════════════════════════════════════════════════════════

Run:  git diff HEAD~1 -- {feature_dir}/docs/spec/
(HEAD~1, not HEAD: the caller commits the spec change BEFORE dispatching
this subagent, so HEAD already includes the spec edit and the working tree
is clean. `git diff HEAD` would always be empty; HEAD~1 is the pre-spec
state, which makes the actual spec delta visible.)
Read the diff carefully. If an impl-suggestion was provided, read it now.
Summarise what has changed and what the implementation must achieve before proceeding.

{human_approval_section}
════════════════════════════════════════════════════════════════════════
STEP 3 — LOCK
════════════════════════════════════════════════════════════════════════

Set the scope marker as your FIRST write action — and ONLY that:
  touch {repo_root}/.rabbit-scope-active-{feature_name}

Do NOT register a `trap '... rm -f ...' EXIT` here. Each Claude Code Bash
tool invocation runs in a separate (per-call) shell process. The trap would
fire the moment that shell exits — i.e., immediately after `touch` returns —
deleting the scope marker before any subsequent step (TEST-WRITE, IMPLEMENT,
etc.) can rely on it. Cleanup is explicit and happens in STEP 9 UNLOCK
(`rm -f {repo_root}/.rabbit-scope-active-{feature_name}`), AFTER the chore
commit and BEFORE the HANDOFF block.

════════════════════════════════════════════════════════════════════════
STEP 4 — TEST-WRITE
════════════════════════════════════════════════════════════════════════

1. Read all existing tests in {feature_dir}/test/
2. Compare each spec behaviour against existing tests.
3. For each behaviour with no e2e test: add one now. (E2E TEST RULE applies.)
4. Commit new/updated tests:
   git add {feature_dir}/test/
   git commit -m "test({feature_name}): add e2e tests for spec behaviours"

Note on ordering: the commit above happens BEFORE STEP 5 (TEST-RED) runs.
That is intentional — STEP 5 verifies the suite is failing as expected after
the commit. The tests are committed in their failing state so the diff is
captured atomically alongside the implementation that will turn them green.

════════════════════════════════════════════════════════════════════════
STEP 5 — TEST-RED
════════════════════════════════════════════════════════════════════════

Run: python3 {feature_dir}/test/run.py
Verify tests FAIL. If they already pass (no implementation gap), document why and proceed.

Bring tdd_state into this cycle from the prior cycle's `test-green` endpoint.
The tdd-step.py state machine is forward-only; from `test-green` the only
valid path into a new cycle starts with `spec-update`. Run this BEFORE the
`test-red` transition below. If the starting state is already `spec-update`
or further along, the transition is a no-op-friendly check via `show` first:

  CURRENT_STATE=$(python3 {tdd_step_py} show {feature_dir})
  if [ "$CURRENT_STATE" = "test-green" ]; then
    python3 {tdd_step_py} transition {feature_dir} spec-update
  fi

Advance state:
  python3 {tdd_step_py} transition {feature_dir} test-red

════════════════════════════════════════════════════════════════════════
STEP 6 — IMPLEMENT
════════════════════════════════════════════════════════════════════════

Max iterations: {args.max_iterations}

IMPORTANT: Before issuing any Edit/Write tool call against an existing file,
Read it in this session first. The Claude Code Edit tool rejects Edits on
un-Read files (tdd-subagent Inv 18). This constraint applies to any file
you edit.

Loop (repeat until green or max iterations reached):
  1. Write/update implementation files for {feature_name}
  2. Run: python3 {feature_dir}/test/run.py
  3. If tests pass:
       a. git add {feature_dir}/
       b. git commit -m "fix({feature_name}): <one-line summary>"
          (use `feat(...)` instead of `fix(...)` when introducing a new
          feature rather than fixing a bug)
       c. break loop
  4. If iteration == {args.max_iterations}: emit this HANDOFF and stop:
       HANDOFF:
         feature: {feature_name}
         tdd_state: impl
         test_result: fail
         failure_reason: max_iterations_reached
         tdd_report_path: null
         notes: Reached {args.max_iterations} iterations without test-green

The implementation commit MUST happen INSIDE the loop, BEFORE the
`tdd-step.py transition ... impl` call below. Otherwise the impl SHA
captured in STEP 8 (via `git rev-parse HEAD`) would point at the prior
test commit from STEP 4, not at the actual implementation.

On success — advance state (only AFTER the impl commit above):
  python3 {tdd_step_py} transition {feature_dir} impl
  python3 {tdd_step_py} transition {feature_dir} test-green

════════════════════════════════════════════════════════════════════════
STEP 7 — CODE-REVIEW
════════════════════════════════════════════════════════════════════════

Invoke: Skill("superpowers:requesting-code-review")
The review covers ALL changed files: tests and functional code.
(The skill name is exact and case-sensitive. The bare `superpowers:code-reviewer`
form does not exist — using it silently no-ops the review step.)

{code_review_loop_note}

════════════════════════════════════════════════════════════════════════
STEP 8 — TEST-GREEN
════════════════════════════════════════════════════════════════════════

Run final test suite to confirm pass:
  python3 {feature_dir}/test/run.py

FIRST — capture the implementation commit SHA BEFORE STEP 9's chore commit:
  IMPL_SHA=$(git rev-parse HEAD)

This ordering is non-negotiable. STEP 9's `chore({feature_name}): advance
tdd_state to test-green` commit will advance HEAD past the implementation
commit; capturing `git rev-parse HEAD` after that point would record the
chore SHA in `impl_commit`, not the actual implementation SHA. The
tdd-report MUST be fully written with the captured `$IMPL_SHA` value
substituted into `impl_commit` BEFORE STEP 9 UNLOCK begins.

Write tdd-report (gitignored — NEVER commit):
  mkdir -p {repo_root}/.rabbit/
  Path: {repo_root}/.rabbit/tdd-report-{feature_name}.json

IMPORTANT: the JSON below is a TEMPLATE. You MUST substitute actual values
for every `<...>` placeholder and for `$IMPL_SHA`. Do NOT copy the template
literally — replace the placeholders with the real values you have just
captured. Specifically: replace `$IMPL_SHA` with the captured commit SHA,
`<yes|no>` with `yes` or `no`, `<reason or null>` with the actual reason
string or the JSON literal `null`, and so on.

  {{
    "schema_version": "1.0.0",
    "feature": "{feature_name}",
    "linked_item": "{linked_item_value}",
    "item_type": "{item_type_value}",
    "spec_changes": "<yes|no>",
    "spec_no_change_reason": "<reason or null>",
    "impl_summary": "<one paragraph describing what was implemented>",
    "spec_compliance": "<pass|fail>",
    "spec_compliance_notes": "<unaddressed invariants or null>",
    "test_result": "pass",
    "tdd_state": "test-green",
    "impl_commit": "$IMPL_SHA"
  }}

════════════════════════════════════════════════════════════════════════
STEP 9 — UNLOCK
════════════════════════════════════════════════════════════════════════

Before emitting HANDOFF, commit the tdd_state transition so the dispatcher
does not have to commit feature.json manually:

  git add {feature_dir}/feature.json
  git commit -m "chore({feature_name}): advance tdd_state to test-green"
{close_calls_block}
Remove the scope marker explicitly (no `trap` was registered at LOCK — see
the explanation in STEP 3 about per-call shell process semantics):
  rm -f {repo_root}/.rabbit-scope-active-{feature_name}

════════════════════════════════════════════════════════════════════════
HANDOFF (emit on completion)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: {feature_name}
  tdd_state: test-green
  test_result: pass
  spec_compliance: <pass|fail>
  tdd_report_path: {repo_root}/.rabbit/tdd-report-{feature_name}.json
  notes: <brief summary>{handoff_closed_items_block}

Also emit the structured JSON HANDOFF below. The JSON block is the
machine-first source of truth (philosophy.md §1); the YAML-like form above
is the human-readable view alongside the machine-first JSON. Substitute
every `<...>` placeholder with the actual value before emitting.

HANDOFF_JSON:
```json
{{
  "handoff_schema_version": "1.0.0",
  "feature": "{feature_name}",
  "tdd_state": "test-green",
  "test_result": "pass",
  "spec_compliance": "<pass|fail>",
  "tdd_report_path": "{repo_root}/.rabbit/tdd-report-{feature_name}.json",
  "closed_items": {handoff_closed_items_json},
  "notes": "<brief summary>"
}}
```
"""

    sys.stdout.write(prompt)
    sys.stderr.write(f"dispatch-tdd-subagent: prompt ready for feature '{feature_name}'\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
