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
# Version: 4.4.0
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when TDD cycle is natively supported by rabbit CLI.

import argparse
import os
import re
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
# Issue #336 Phase 1: the bypass is dual-read — EITHER marker name is valid
# during the coexistence window, so the note names both forms.
_BYPASS_NOTE_TEXT = (
    "NOTE: human-approval bypass marker is active "
    "(.rabbit-human-approval-bypass or .rabbit-tdd-autonomous). The "
    "dispatcher's Step 4 HUMAN-APPROVAL gate was skipped for this "
    "dispatch. Revoke via `/rabbit-config human-approval true`."
)


def _tdd_report_path(repo_root, feature_name):
    """Per-mode canonical tdd-report absolute path (Inv 48).

    Plugin mode: `repo_root` IS the rabbit_root, so the report sits at
      <repo_root>/tdd-report-<feature>.json
    (NO extra `.rabbit/` segment; that would double-up to
    `<host>/.rabbit/.rabbit/tdd-report-...json` which is the #313 bug.)

    Standalone: `repo_root` is the git toplevel; report sits under
      <repo_root>/.rabbit/tdd-report-<feature>.json

    Mode detection mirrors _scope_marker_path's dual-candidate check:
    look for a `mode` marker either at `<repo_root>/.runtime/mode`
    (plugin where repo_root==rabbit_root) or at
    `<repo_root>/.rabbit/.runtime/mode` (plugin where repo_root==host).
    """
    candidates = (
        # Plugin mode where repo_root is RABBIT_ROOT (per Inv 47).
        (os.path.join(repo_root, ".runtime", "mode"),
         os.path.join(repo_root, f"tdd-report-{feature_name}.json")),
        # Plugin mode where repo_root is the host project root.
        (os.path.join(repo_root, ".rabbit", ".runtime", "mode"),
         os.path.join(repo_root, ".rabbit", f"tdd-report-{feature_name}.json")),
    )
    for mode_file, plugin_path in candidates:
        try:
            with open(mode_file) as f:
                if f.read().strip() == "plugin":
                    return plugin_path
        except (OSError, IOError):
            continue
    return os.path.join(repo_root, ".rabbit", f"tdd-report-{feature_name}.json")


def _scope_marker_path(repo_root, feature_name):
    """Per-mode scope-marker absolute path (Inv 12 mode-aware amendment).

    Standalone (mode marker absent or != 'plugin'):
      <repo_root>/.rabbit-scope-active-<feature>
    Plugin (mode marker == 'plugin'):
      <rabbit_root>/.runtime/scope-active-<feature>

    The dispatcher's `repo_root` differs by mode (per Inv 47):
      - standalone: `repo_root` is the git toplevel; mode marker would be
        at `<repo_root>/.rabbit/.runtime/mode`.
      - plugin: `repo_root` is `RABBIT_ROOT` (which IS `<host>/.rabbit/`);
        mode marker is at `<repo_root>/.runtime/mode`.
    Both locations are checked so plugin-mode dispatches (where
    `repo_root` is already the rabbit-root) and standalone-mode dispatches
    (where `repo_root` is the git toplevel) both reach the right answer.
    Mirrors rabbit-cage Inv 17(b) so scope-guard finds the marker at the
    path it expects for the current install mode.
    """
    candidates = (
        # Plugin mode where repo_root is RABBIT_ROOT (per Inv 47).
        (os.path.join(repo_root, ".runtime", "mode"),
         os.path.join(repo_root, ".runtime", f"scope-active-{feature_name}")),
        # Plugin mode where repo_root is the host project root.
        (os.path.join(repo_root, ".rabbit", ".runtime", "mode"),
         os.path.join(repo_root, ".rabbit", ".runtime",
                      f"scope-active-{feature_name}")),
    )
    for mode_file, plugin_path in candidates:
        try:
            with open(mode_file) as f:
                if f.read().strip() == "plugin":
                    return plugin_path
        except (OSError, IOError):
            continue
    return os.path.join(repo_root, f".rabbit-scope-active-{feature_name}")


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


def _parse_invariants_section(spec_text):
    """Locate the ## Invariants section in a spec.md and parse its
    invariant bodies (Inv 49(c)).

    Returns a tuple `(preamble, header_line, invariants, footer)`:
      - preamble: text up to and including the line BEFORE the
        `## Invariants` heading.
      - header_line: the literal `## Invariants` line (preserved as-is).
      - invariants: dict mapping `int` invariant number -> body text
        (number line through line before next invariant number, or
        through end of section if last). Includes retired tombstones.
      - footer: text from the NEXT `## ` heading (or EOF) onward.

    Returns `None` if the spec has no `## Invariants` section.
    """
    m = re.search(r"^## Invariants\s*$", spec_text, re.MULTILINE)
    if not m:
        return None
    header_start = m.start()
    header_line_end = spec_text.find("\n", m.end())
    if header_line_end == -1:
        header_line_end = len(spec_text)
    header_line = spec_text[header_start:header_line_end + 1]
    # Find next ## heading (section end). Search after header_line_end.
    nxt = re.search(r"^## ", spec_text[header_line_end + 1:], re.MULTILINE)
    if nxt:
        section_end = header_line_end + 1 + nxt.start()
    else:
        section_end = len(spec_text)
    preamble = spec_text[:header_start]
    body = spec_text[header_line_end + 1:section_end]
    footer = spec_text[section_end:]
    # Find invariant boundaries: lines starting with `N. ` at line-start.
    boundaries = []
    for bm in re.finditer(r"^([0-9]+)\.\s", body, re.MULTILINE):
        boundaries.append((int(bm.group(1)), bm.start()))
    invariants = {}
    for i, (num, start) in enumerate(boundaries):
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(body)
        invariants[num] = body[start:end]
    return preamble, header_line, invariants, footer


def _spec_grep_hint(repo_root, spec_path, feature_name):
    """Repo-relative path used in the scoped-view grep NOTE (dual-read).

    Prefers the actual --spec path the caller resolved (this already
    points at the flat docs/ layout for migrated features and at specs/
    or the legacy docs/spec/ layout otherwise). When --spec is not under
    repo_root (e.g. a tempdir in tests) the hint falls back to the
    feature's canonical doc: the flat docs/spec.md layout if that file
    exists under repo_root, else the specs/spec.md layout.
    """
    if spec_path and repo_root:
        try:
            rel = os.path.relpath(os.path.abspath(spec_path),
                                  os.path.abspath(repo_root))
            if not rel.startswith(".."):
                return rel
        except Exception:
            pass
    docs_rel = f".claude/features/{feature_name}/docs/spec.md"
    if repo_root and os.path.isfile(os.path.join(repo_root, docs_rel)):
        return docs_rel
    return f".claude/features/{feature_name}/specs/spec.md"


def _scoped_spec(spec_text, requested, feature_name, grep_hint):
    """Build a scoped spec_content with only the requested invariants
    (Inv 49). Returns (scoped_text, error_message). On unknown
    invariant numbers, returns (None, error_message)."""
    parsed = _parse_invariants_section(spec_text)
    if parsed is None:
        return None, (f"--affected-invariants: spec for '{feature_name}' "
                      "has no ## Invariants section")
    preamble, header_line, invariants, footer = parsed
    unknown = [n for n in requested if n not in invariants]
    if unknown:
        available = sorted(invariants.keys())
        return None, (
            f"error: --affected-invariants includes unknown invariant "
            f"number(s) for {feature_name}: {unknown}; available: "
            f"{available}"
        )
    ordered = sorted(set(requested))
    blocks = [invariants[n].rstrip() for n in ordered]
    note = (
        f"> NOTE: scoped view of {len(ordered)} selected invariants "
        f"({ordered}) from {feature_name} spec.md; for related-but-"
        f"unembedded invariants run "
        f"`grep '^<num>\\.' {grep_hint}` "
        "against the spec."
    )
    scoped_body = "\n\n".join(blocks) + "\n\n" + note + "\n"
    return preamble + header_line + "\n" + scoped_body + "\n" + footer, None


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
                     "8-step TDD cycle (test-red -> impl -> test-green) for "
                     "ONE feature. Prompt is written to stdout."),
    )
    parser.add_argument("--scope", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--impl-suggestion", default=None)
    parser.add_argument(
        "--affected-invariants", default=None,
        help=("comma-separated invariant numbers (e.g. 4,16,22); when "
              "provided, embed only those invariants from the spec's "
              "## Invariants section instead of the full spec (Inv 49)"),
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
            "[--impl-suggestion <path>] "
            "[--affected-invariants N[,N,...]] "
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
    # Inv 49: when --affected-invariants is provided, replace the
    # ## Invariants section body with only the requested invariants
    # plus a NOTE line. Default (flag omitted) preserves the full
    # spec embed unchanged.
    if args.affected_invariants is not None:
        try:
            requested = sorted({int(n) for n in
                                args.affected_invariants.split(",")
                                if n.strip()})
        except ValueError:
            sys.stderr.write(
                "error: --affected-invariants must be a comma-separated "
                f"list of integers; got: {args.affected_invariants!r}\n"
            )
            return 1
        grep_hint = _spec_grep_hint(repo_root, args.spec, feature_name)
        scoped, err = _scoped_spec(spec_content, requested, feature_name,
                                   grep_hint)
        if err:
            sys.stderr.write(err + "\n")
            return 1
        spec_content = scoped
    impl_suggestion_block = ""
    if args.impl_suggestion:
        raw = _read_file(args.impl_suggestion)
        if raw != "(not found)":
            impl_suggestion_block = f"\n## Implementation Suggestion\n\n```json\n{raw}\n```\n"

    # Emit the bypass-marker preamble note when the human-approval
    # bypass marker exists at the repo root (Inv 23). Issue #336 Phase 1:
    # dual-read — the bypass is active when EITHER
    # `.rabbit-human-approval-bypass` OR `.rabbit-tdd-autonomous` exists.
    # The note appears on every dispatch while a marker is present; it
    # does not consume the marker. rabbit_print is the sole emission path
    # (Inv 24) — no inline ANSI/brand strings in this file.
    bypass_marker_paths = (
        os.path.join(repo_root, ".rabbit-human-approval-bypass"),
        os.path.join(repo_root, ".rabbit-tdd-autonomous"),
    )
    if any(os.path.isfile(p) for p in bypass_marker_paths):
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

    # Inv 58 (issue #527): the four filesystem-path slots are emitted
    # repo-RELATIVE (os.path.relpath(<abs>, repo_root)) and repo_root is
    # emitted as '.'. The subagent resolves every baked path from its CURRENT
    # WORKING DIRECTORY, so a worktree-isolated dispatch (rabbit-auto-evolve
    # Inv 28) operates on its own tree instead of the main repo. The absolute
    # computations above are retained because the mode-aware helpers
    # (_scope_marker_path / _tdd_report_path) and the find-feature lookup need
    # real absolute paths to os.path.exists markers at assembly time; only the
    # emitted SLOT STRINGS are relativized.
    slots = {
        "feature_name": feature_name,
        "spec_content": spec_content,
        "impl_suggestion_block": impl_suggestion_block,
        "bypass_preamble_note": bypass_preamble_note,
        "feature_dir": os.path.relpath(feature_dir, repo_root),
        "tdd_step_py": os.path.relpath(tdd_step_py, repo_root),
        "repo_root": ".",
        "max_iterations": str(args.max_iterations),
        "code_review_loop_note": code_review_loop_note,
        "scope_marker_path": os.path.relpath(
            _scope_marker_path(repo_root, feature_name), repo_root),
        "tdd_report_path": os.path.relpath(
            _tdd_report_path(repo_root, feature_name), repo_root),
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
