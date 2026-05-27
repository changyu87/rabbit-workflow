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
# Version: 4.0.0
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
# The note refers to the DISPATCHER's Step 4 HUMAN-APPROVAL gate (owned by
# rabbit-feature-touch), not any step inside the assembled subagent prompt.
# The subagent itself no longer contains a HUMAN-APPROVAL step
# (TDD-SUBAGENT-BACKLOG-19 retired Inv 25, 26).
_BYPASS_NOTE_TEXT = (
    "NOTE: human-approval bypass marker is active "
    "(.rabbit-human-approval-bypass). The dispatcher's Step 4 "
    "HUMAN-APPROVAL gate was skipped for this dispatch. Revoke via "
    "`/rabbit-config human-approval true`."
)


def _validate_linked_item(path_str):
    """Inv 30: validate --linked-item path layout.

    Resolves `path_str` and requires the canonical rabbit-file storage
    layout `.../rabbit/features/<feature>/<bugs|backlogs>/<id>/`. On
    failure, writes a diagnostic naming both the expected layout and the
    observed path tail to stderr and exits 2 (BEFORE any stdout). On
    success, returns the validated feature name (the segment at -3) so
    callers can wire it through the close-call block (Inv 19).
    """
    resolved = _Path(path_str).resolve()
    parts = resolved.parts
    if len(parts) < 4 or parts[-4] != "features" or parts[-2] not in ("bugs", "backlogs"):
        tail = "/".join(parts[-4:]) if len(parts) >= 4 else "/".join(parts)
        sys.stderr.write(
            "ERROR: --linked-item path layout invalid: "
            "expected `.../rabbit/features/<feature>/<bugs|backlogs>/<id>/`; "
            f"observed tail: {tail}\n"
        )
        sys.exit(2)
    return parts[-3]


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
                     "7-step TDD cycle (test-red -> impl -> test-green) for "
                     "ONE feature. Prompt is written to stdout."),
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
            "[--code-review-full-loop] [--max-iterations N]\n"
        )
        return 2

    if args.linked_item and not args.item_type:
        sys.stderr.write("ERROR: --linked-item requires --item-type\n")
        return 2
    if args.item_type and not args.linked_item:
        sys.stderr.write("ERROR: --item-type requires --linked-item\n")
        return 2
    # Inv 30: validate --linked-item path layout BEFORE any stdout. The
    # helper exits(2) with a stderr diagnostic on failure; on success it
    # returns the validated feature name (segments[-3]) for use in the
    # close-call block below (Inv 19).
    validated_feature_from_link = None
    if args.linked_item:
        validated_feature_from_link = _validate_linked_item(args.linked_item)
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
    tdd_step_py = os.path.join(repo_root, ".claude", "features", "tdd-subagent", "scripts", "tdd-step.py")

    spec_content = _read_file(args.spec)
    impl_suggestion_block = ""
    if args.impl_suggestion:
        raw = _read_file(args.impl_suggestion)
        if raw != "(not found)":
            impl_suggestion_block = f"\n## Implementation Suggestion\n\n```json\n{raw}\n```\n"

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

    # Build close-call block for STEP 7 UNLOCK (Inv 19/20: all close
    # calls route through rabbit-file's `item-status.py set ...`). One
    # loop, one template — primary and secondary differ only by comment,
    # reason, and the HANDOFF label string. Baseline prompt (no items)
    # is unchanged.
    items = []
    if args.linked_item and args.item_type:
        # Inv 30: feature/id come from the validated resolved path so the
        # downstream item-status.py call cannot drift from the actual
        # storage layout. validated_feature_from_link is set above.
        resolved_parts = _Path(args.linked_item).resolve().parts
        feat = validated_feature_from_link
        iid = resolved_parts[-1]
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

    if args.code_review_full_loop:
        code_review_loop_note = (
            "--code-review-full-loop is active: after any code changes from CODE-REVIEW, "
            "loop back to Step 2 (TEST-WRITE) and repeat until CODE-REVIEW produces no further changes."
        )
    else:
        code_review_loop_note = (
            "Default mode: use judgment — loop back to Step 2 (TEST-WRITE) only if "
            "CODE-REVIEW changed functional code or tests."
        )

    slots = {
        "feature_name": feature_name,
        "spec_content": spec_content,
        "impl_suggestion_block": impl_suggestion_block,
        "bypass_preamble_note": bypass_preamble_note,
        "feature_dir": feature_dir,
        "tdd_step_py": tdd_step_py,
        "repo_root": repo_root,
        "max_iterations": str(args.max_iterations),
        "code_review_loop_note": code_review_loop_note,
        "linked_item_value": linked_item_value,
        "item_type_value": item_type_value,
        "close_calls_block": close_calls_block,
        "handoff_closed_items_block": handoff_closed_items_block,
        "handoff_closed_items_json": handoff_closed_items_json,
    }
    build_prompt_py = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "build-prompt.py",
    )
    slot_args = []
    for k, v in slots.items():
        slot_args.extend(["--slot", f"{k}={v}"])
    res = subprocess.run(
        [sys.executable, build_prompt_py, "--callable-id", "tdd-subagent", *slot_args],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        return res.returncode
    prompt_file = res.stdout.strip()
    try:
        with open(prompt_file) as f:
            sys.stdout.write(f.read())
    except OSError as e:
        sys.stderr.write(f"ERROR: cannot read assembled prompt at {prompt_file}: {e}\n")
        return 1
    sys.stderr.write(f"dispatch-tdd-subagent: prompt ready for feature '{feature_name}'\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
