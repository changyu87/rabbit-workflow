#!/usr/bin/env python3
# tdd-step.py — read and transition the tdd_state of a feature.
#
# Usage:
#   tdd-step.py show <feature-dir>
#   tdd-step.py next <feature-dir>
#   tdd-step.py transitions <feature-dir>
#   tdd-step.py transition <feature-dir> <new-state> [--force] [--spec-no-change-reason <reason>]
#
# Exit:
#   0 success
#   1 transition denied or invalid input
#   2 invocation error

import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path as _Path

# Pull in the centralized [rabbit] print renderer from the contract feature
# (TDD-SUBAGENT-BACKLOG-11; spec Inv 5). tdd-step.py lives at
# .claude/features/tdd-subagent/scripts/, so parents[2] = .claude/features/.
_CONTRACT_SCRIPTS = _Path(__file__).resolve().parents[2] / "contract" / "scripts"
if str(_CONTRACT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CONTRACT_SCRIPTS))
from rabbit_print import rabbit_block, rabbit_subline, tdd_transition, tdd_forced  # noqa: E402


def _rbt_ok(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _rbt_alert(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def _repo_root():
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return env
    script_dir = os.path.dirname(os.path.abspath(__file__))
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


REPO_ROOT = _repo_root()


def usage():
    sys.stderr.write(
        "usage:\n"
        "  tdd-step.py show <feature-dir>\n"
        "  tdd-step.py next <feature-dir>\n"
        "  tdd-step.py transitions <feature-dir>\n"
        "  tdd-step.py transition <feature-dir> <new-state> [--force] [--spec-no-change-reason <reason>]\n"
    )


_FORWARD = {
    "spec":        "spec-update",
    "spec-update": "test-red",
    "test-red":    "impl",
    "impl":        "test-green",
    "test-green":  "deprecated",
    "deprecated":  "",
}

# Alternate forward transitions. Each state's primary next is in _FORWARD;
# additional valid forward targets (no --force required) are listed here.
# test-green has two valid forward paths: deprecated (retirement) and
# spec-update (next cycle restart, e.g. for rabbit-feature-touch).
_FORWARD_ALT = {
    "test-green": ["spec-update"],
}

_VALID_STATES = {"spec", "spec-update", "test-red", "impl", "test-green", "deprecated"}


def forward_next(state):
    return _FORWARD.get(state, "")


def forward_targets(state):
    """Return the list of all valid forward targets from `state` (no --force).

    The primary target (from _FORWARD) comes first; alternates follow.
    Returns [] when state is terminal.
    """
    targets = []
    primary = _FORWARD.get(state, "")
    if primary:
        targets.append(primary)
    for alt in _FORWARD_ALT.get(state, []):
        if alt and alt not in targets:
            targets.append(alt)
    return targets


def is_valid_state(state):
    return state in _VALID_STATES


def _feature_json_path(d):
    return os.path.join(d, "feature.json")


def read_state(d):
    fj = _feature_json_path(d)
    if not os.path.isfile(fj):
        sys.stderr.write(f"ERROR: no feature.json in {d}\n")
        return None, 2
    try:
        with open(fj, "r") as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"ERROR: failed to parse {fj}: {e}\n")
        return None, 2
    return data.get("tdd_state", "") or "", 0


def write_state(d, new, spec_no_change_reason=""):
    fj = _feature_json_path(d)
    with open(fj, "r") as f:
        data = json.load(f)
    data["tdd_state"] = new
    data["updated"] = date.today().isoformat()
    if spec_no_change_reason:
        data["spec_no_change_reason"] = spec_no_change_reason
    # Atomic write: stage to a temp file in the same directory, then rename.
    # The same-directory tempfile guarantees os.replace is a true atomic rename
    # on POSIX filesystems and avoids cross-device move issues.
    fd, tmp = tempfile.mkstemp(prefix=".feature.json.", dir=os.path.dirname(fj) or ".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, fj)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _head_sha():
    """Return the resolved HEAD commit SHA, or the literal 'HEAD' as a last-resort
    fallback when git is unavailable. Consumers receive a real SHA in the common
    case so audit trails remain accurate."""
    try:
        out = subprocess.run(
            ["git", "-C", REPO_ROOT or ".", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "HEAD"


def auto_close_backlog(d):
    """Auto-close in-progress backlog items for the feature on test-green.

    Backlog storage was unified into rabbit-file (the `bug-backlog-files`
    branch). Items are no longer kept in `.claude/backlogs/<feature>/`;
    the unified `item-status.py` interface owns discovery and writes.
    This is a best-effort no-op when the unified script is unavailable.
    """
    fj = _feature_json_path(d)
    try:
        with open(fj, "r") as f:
            data = json.load(f)
        feature_name = data.get("name", "") or ""
    except Exception:
        return
    if not feature_name:
        return
    item_status = os.path.join(
        REPO_ROOT, ".claude", "features", "rabbit-file", "scripts",
        "item-status.py",
    )
    if not os.path.isfile(item_status):
        return
    # Legacy local backlog dir layout (.claude/backlogs/<feature>/<ID>/item.json)
    # may still exist in transitional repos. When present, iterate and close
    # in-progress items via the unified item-status.py interface. When absent,
    # skip silently — discovery on the bug-backlog-files branch is the caller's
    # responsibility (via --linked-items in dispatch-tdd-subagent.py).
    backlog_dir = os.path.join(REPO_ROOT, ".claude", "backlogs", feature_name)
    if not os.path.isdir(backlog_dir):
        return
    try:
        items = sorted(os.listdir(backlog_dir))
    except Exception:
        return
    head_sha = _head_sha()
    for name in items:
        item_dir = os.path.join(backlog_dir, name)
        item_json = os.path.join(item_dir, "item.json")
        if not os.path.isfile(item_json):
            continue
        try:
            with open(item_json, "r") as f:
                item = json.load(f)
        except Exception:
            continue
        if (item.get("status") or "") != "in-progress":
            continue
        item_id = item.get("name") or name
        try:
            subprocess.run(
                [sys.executable, item_status,
                 "set",
                 "--feature", feature_name,
                 "--type", "backlog",
                 "--id", item_id,
                 "--status", "close",
                 "--reason", "auto-closed by tdd-step.py test-green",
                 "--fix-commits", head_sha],
                capture_output=True, check=False,
            )
        except Exception:
            pass


def _run_enforcement_checks(d, repo_root):
    enforcement_dir = os.path.join(repo_root, ".claude", "features", "contract", "scripts", "enforcement")
    if not os.path.isdir(enforcement_dir):
        return

    def _run(script, args, warn_msg):
        path = os.path.join(enforcement_dir, script)
        if not os.path.isfile(path):
            return
        try:
            res = subprocess.run(
                [sys.executable, path] + args,
                capture_output=True, check=False,
            )
            if res.returncode != 0 and warn_msg:
                _rbt_alert(rabbit_block(rabbit_subline(warn_msg, color="red")))
        except Exception:
            if warn_msg:
                _rbt_alert(rabbit_block(rabbit_subline(warn_msg, color="red")))

    _run("check-tests-non-interactive.py", [d],
         f"WARNING: R3 check failed for {d} — tests may have interactive constructs")
    _run("check-sentinel.py", [d], "")
    _run("check-naming.py", [d], f"WARNING: naming check failed for {d}")
    _run("check-imports-resolve.py", [d], f"WARNING: R-import-resolve check failed for {d}")
    _run("check-symlinks-resolve.py", [repo_root], "WARNING: symlink-resolve check failed")
    _run("check-template-schema-producer-consistency.py", [],
         "WARNING: template-schema-producer consistency check failed")


def _post_test_green_hooks(d):
    _run_enforcement_checks(d, REPO_ROOT)
    # Project consolidate is a best-effort hook gated by project-map.json. The
    # outer try/except guards against any unexpected failure (missing script,
    # broken project layout, etc.) so a test-green transition is never blocked
    # by a project-side issue.
    try:
        features_dir = os.path.dirname(os.path.abspath(d))
        project_dir = os.path.dirname(features_dir)
        project_map = os.path.join(project_dir, "project-map.json")
        if os.path.isfile(project_map):
            project_name = os.path.basename(project_dir)
            onboard_py = os.path.join(
                REPO_ROOT, ".claude", "features", "rabbit-cage", "scripts", "rabbit-project.py",
            )
            if os.path.isfile(onboard_py):
                try:
                    subprocess.run(
                        [sys.executable, onboard_py, "consolidate", project_name],
                        capture_output=True, check=False,
                    )
                except Exception:
                    pass
    except Exception:
        pass
    try:
        auto_close_backlog(d)
    except Exception:
        pass


def cmd_show(args):
    if not args:
        usage(); return 2
    d = args[0]
    state, rc = read_state(d)
    if rc != 0:
        return rc
    print(state)
    return 0


def cmd_next(args):
    if not args:
        usage(); return 2
    d = args[0]
    state, rc = read_state(d)
    if rc != 0:
        return rc
    n = forward_next(state)
    if not n:
        sys.stderr.write(f"ERROR: {state} is terminal, no forward state\n")
        return 1
    print(n)
    return 0


def cmd_transitions(args):
    if not args:
        usage(); return 2
    d = args[0]
    state, rc = read_state(d)
    if rc != 0:
        return rc
    targets = forward_targets(state)
    if not targets:
        print("(terminal)")
    else:
        print(" ".join(targets))
    return 0


def cmd_transition(args):
    if len(args) < 2:
        usage(); return 2
    d = args[0]
    new = args[1]
    rest = args[2:]
    force = False
    spec_no_change_reason = ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--force":
            force = True
            i += 1
        elif a == "--spec-no-change-reason":
            if i + 1 >= len(rest) or not rest[i + 1]:
                sys.stderr.write("ERROR: --spec-no-change-reason requires a non-empty reason\n")
                return 2
            spec_no_change_reason = rest[i + 1]
            i += 2
        else:
            sys.stderr.write(f"ERROR: unknown flag '{a}'\n")
            return 2

    if not is_valid_state(new):
        sys.stderr.write(f"ERROR: '{new}' is not a valid tdd_state\n")
        return 1
    cur, rc = read_state(d)
    if rc != 0:
        return rc
    expected = forward_next(cur)
    valid_forward = forward_targets(cur)

    if cur == "spec-update" and new == "test-red":
        if not spec_no_change_reason:
            spec_diff = ""
            try:
                res = subprocess.run(
                    ["git", "-C", REPO_ROOT, "diff", "HEAD", "--", os.path.join(d, "docs", "spec") + os.sep],
                    capture_output=True, text=True, check=False,
                )
                spec_diff = res.stdout if res.returncode == 0 else ""
            except Exception:
                spec_diff = ""
            if not spec_diff:
                sys.stderr.write(
                    "ERROR: spec-update -> test-red requires spec changes (git diff) or --spec-no-change-reason <reason>\n"
                )
                return 1

    if cur == "deprecated":
        sys.stderr.write(f"ERROR: '{cur}' is terminal; cannot transition (even with --force)\n")
        return 1

    if new in valid_forward:
        write_state(d, new, spec_no_change_reason=spec_no_change_reason)
        if new == "test-green":
            _post_test_green_hooks(d)
        _rbt_ok(rabbit_block(tdd_transition(cur, new)))
        return 0

    if force:
        write_state(d, new, spec_no_change_reason=spec_no_change_reason)
        if new == "test-green":
            _post_test_green_hooks(d)
        _rbt_alert(rabbit_block(tdd_forced(cur, new)))
        _rbt_ok(rabbit_block(tdd_transition(cur, new)))
        return 0

    forward_msg = " or ".join(valid_forward) if valid_forward else "(terminal)"
    sys.stderr.write(
        f"ERROR: {cur} -> {new} not allowed (forward expected: {forward_msg}). Use --force to override.\n"
    )
    return 1


def main(argv):
    if len(argv) < 1:
        usage(); return 2
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "show":
        return cmd_show(rest)
    if cmd == "next":
        return cmd_next(rest)
    if cmd == "transitions":
        return cmd_transitions(rest)
    if cmd == "transition":
        return cmd_transition(rest)
    if cmd in ("", "-h", "--help", "help"):
        usage()
        return 0
    sys.stderr.write(f"ERROR: unknown subcommand '{cmd}'\n")
    usage()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
