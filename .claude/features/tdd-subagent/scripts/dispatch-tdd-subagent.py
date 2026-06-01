#!/usr/bin/env python3
# dispatch-tdd-subagent.py — assembles the prompt for a per-feature TDD subagent.
#
# Usage:
#   dispatch-tdd-subagent.py \
#     --scope <feature-name> \
#     --spec <spec-path> \
#     [--impl-suggestion <path>] \
#     [--code-review-full-loop] \
#     [--max-iterations N]
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
            "[--impl-suggestion <path>] "
            "[--code-review-full-loop] [--max-iterations N]\n"
        )
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
