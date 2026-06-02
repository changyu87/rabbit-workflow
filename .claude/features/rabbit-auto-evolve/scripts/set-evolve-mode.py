#!/usr/bin/env python3
"""set-evolve-mode.py — compound mutator for auto-evolve mode activation.

Usage:
  set-evolve-mode.py on    # flip human-approval=false, bypass-permissions=true,
                           # write .rabbit-auto-evolve-active
  set-evolve-mode.py off   # reverse all three in inverse order

Per rabbit-auto-evolve spec.md Inv 1, executes three deterministic mutations
in order (and the inverse order on `off`); on any step failure, aborts and
best-effort rolls back any prior steps; reports the failed step on stderr.
Exit 0 on full success, non-zero on any step failure (after rollback attempt).
Idempotent in the steady state (delegated to contract.lib.mutation primitives).

Version: 1.2.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import os
import sys

MARKER_BYPASS = ".rabbit-human-approval-bypass"
MARKER_BYPASS_CONTENT = "session"
SETTINGS_FILE = ".claude/settings.local.json"
SETTINGS_KEY = "permissions.defaultMode"
SETTINGS_VALUE = "bypassPermissions"
MARKER_ACTIVE = ".rabbit-auto-evolve-active"
MARKER_ACTIVE_CONTENT = ""
# Inv 1 v0.7.1 (issue #371): on `off`, also delete the four loop-runtime
# markers (innermost first) before reversing the three activation mutations,
# so a subsequent `on` lands in a clean state. Deletion is idempotent
# (delete-if-exists; missing markers are no-ops; no rollback bookkeeping
# needed for this step because delete_marker on a missing path passes).
LOOP_RUNTIME_MARKERS = (
    ".rabbit-auto-evolve-running",
    ".rabbit-auto-evolve-stop-requested",
    ".rabbit-auto-evolve-restart-needed",
    ".rabbit-auto-evolve-aborted",
)


def _import_mutation():
    """Lazy-import contract.lib.mutation by inserting the contract feature
    dir onto sys.path. The contract dir is resolved relative to this
    script's location (not cwd) so the import works regardless of where
    the script is invoked from. Mirrors the pattern used by rabbit-config.py."""
    here = os.path.dirname(os.path.abspath(__file__))
    # scripts/ -> rabbit-auto-evolve/ -> features/ -> .claude/
    contract_dir = os.path.normpath(os.path.join(here, "..", "..", "contract"))
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    from lib import mutation  # noqa: PLC0415
    return mutation


def _import_rabbit_print():
    """Lazy-import rabbit_print from the contract feature's scripts dir.
    Mirrors the sys.path-insert pattern used by rabbit-config.py for the
    same module — contract scripts dir is not on sys.path by default."""
    here = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.normpath(
        os.path.join(here, "..", "..", "contract", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from rabbit_print import rabbit_print  # noqa: PLC0415
    return rabbit_print


class StepError(RuntimeError):
    """Raised when a mutation step fails. `label` is the human-readable
    step descriptor (e.g. 'step 2 (set_json_key ...)'); `detail` is the
    inner error message (from CheckResult or from the exception)."""

    def __init__(self, label, detail):
        super().__init__(f"{label}: {detail}")
        self.label = label
        self.detail = detail


def _do(label, fn, *args, **kwargs):
    """Invoke fn(*args, **kwargs); wrap any raised exception OR non-passed
    CheckResult into StepError(label, ...). Returns the CheckResult on
    success."""
    try:
        result = fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — any raise from the mutation API
                            # is a step-2-style failure we want to label.
        raise StepError(label, f"{type(e).__name__}: {e}") from e
    if not result.passed:
        raise StepError(label, "; ".join(result.messages))
    return result


def _on(mutation, repo_root):
    """Execute the three on-steps in order; rollback any completed step on
    failure. Returns (True, None, None) on success or
    (False, failed_label, err, completed) on failure."""
    # Capture prior defaultMode (if any) so step 2 rollback can restore it
    # instead of unconditionally deleting.
    prior_default_mode = _read_default_mode(repo_root)

    completed = []  # list of (label, rollback_callable) in stack order
    try:
        # Step 1
        _do(
            "step 1 (write_marker .rabbit-human-approval-bypass)",
            mutation.write_marker, MARKER_BYPASS, MARKER_BYPASS_CONTENT, repo_root=repo_root,
        )
        completed.append(("step 1", lambda: mutation.delete_marker(MARKER_BYPASS, repo_root=repo_root)))

        # Step 2
        _do(
            "step 2 (set_json_key permissions.defaultMode=bypassPermissions)",
            mutation.set_json_key, SETTINGS_FILE, SETTINGS_KEY, SETTINGS_VALUE, repo_root=repo_root,
        )
        if prior_default_mode is None:
            completed.append(("step 2", lambda: mutation.delete_json_key(SETTINGS_FILE, SETTINGS_KEY, repo_root=repo_root)))
        else:
            prior = prior_default_mode
            completed.append(("step 2", lambda: mutation.set_json_key(SETTINGS_FILE, SETTINGS_KEY, prior, repo_root=repo_root)))

        # Step 3
        _do(
            "step 3 (write_marker .rabbit-auto-evolve-active)",
            mutation.write_marker, MARKER_ACTIVE, MARKER_ACTIVE_CONTENT, repo_root=repo_root,
        )
        return True, None, None
    except StepError as e:
        return False, e.label, e.detail, completed


def _off(mutation, repo_root):
    """Execute the three off-steps in inverse order; rollback any completed
    step on failure. Returns (True, None, None) on success or
    (False, failed_label, err, completed) on failure."""
    # For rollback of off, capture state we may need to restore.
    bypass_existed = os.path.isfile(os.path.join(repo_root, MARKER_BYPASS))
    bypass_content = None
    if bypass_existed:
        try:
            with open(os.path.join(repo_root, MARKER_BYPASS)) as f:
                bypass_content = f.read()
        except OSError:
            bypass_content = MARKER_BYPASS_CONTENT
    prior_default_mode = _read_default_mode(repo_root)
    active_existed = os.path.isfile(os.path.join(repo_root, MARKER_ACTIVE))
    active_content = None
    if active_existed:
        try:
            with open(os.path.join(repo_root, MARKER_ACTIVE)) as f:
                active_content = f.read()
        except OSError:
            active_content = MARKER_ACTIVE_CONTENT

    completed = []
    try:
        # Step 0 (off, v0.7.1 / Inv 1 / #371): delete the four loop-runtime
        # markers (innermost first). Each call is idempotent; missing markers
        # are no-ops. No rollback bookkeeping for these — re-creating a
        # loop-runtime marker as part of an `off` rollback would be wrong
        # because their presence indicates loop state we are intentionally
        # tearing down.
        for marker in LOOP_RUNTIME_MARKERS:
            _do(
                f"step 0 off (delete_marker {marker})",
                mutation.delete_marker, marker, repo_root=repo_root,
            )

        # Step 1 (off): delete .rabbit-auto-evolve-active
        _do(
            "step 1 off (delete_marker .rabbit-auto-evolve-active)",
            mutation.delete_marker, MARKER_ACTIVE, repo_root=repo_root,
        )
        if active_existed:
            ac = active_content if active_content is not None else MARKER_ACTIVE_CONTENT
            completed.append(("step 1 off", lambda: mutation.write_marker(MARKER_ACTIVE, ac, repo_root=repo_root)))

        # Step 2 (off): delete permissions.defaultMode
        _do(
            "step 2 off (delete_json_key permissions.defaultMode)",
            mutation.delete_json_key, SETTINGS_FILE, SETTINGS_KEY, repo_root=repo_root,
        )
        if prior_default_mode is not None:
            prior = prior_default_mode
            completed.append(("step 2 off", lambda: mutation.set_json_key(SETTINGS_FILE, SETTINGS_KEY, prior, repo_root=repo_root)))

        # Step 3 (off): delete .rabbit-human-approval-bypass
        _do(
            "step 3 off (delete_marker .rabbit-human-approval-bypass)",
            mutation.delete_marker, MARKER_BYPASS, repo_root=repo_root,
        )
        return True, None, None
    except StepError as e:
        return False, e.label, e.detail, completed


def _read_default_mode(repo_root):
    """Read the current permissions.defaultMode value, or None if absent
    (file missing, key missing, or unreadable)."""
    import json  # noqa: PLC0415
    path = os.path.join(repo_root, SETTINGS_FILE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return None
    return perms.get("defaultMode")


def _rollback(completed):
    """Run the rollback closures in reverse order; collect any rollback
    failures into a list of strings."""
    failures = []
    for label, fn in reversed(completed):
        try:
            r = fn()
            if not r.passed:
                failures.append(f"rollback for {label} failed: {'; '.join(r.messages)}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"rollback for {label} raised: {e}")
    return failures


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("on", "off"):
        sys.stderr.write("Usage: set-evolve-mode.py {on|off}\n")
        sys.exit(2)

    action = sys.argv[1]
    repo_root = os.getcwd()

    try:
        mutation = _import_mutation()
    except ImportError as e:
        sys.stderr.write(f"set-evolve-mode: cannot import contract.lib.mutation: {e}\n")
        sys.exit(1)

    if action == "on":
        result = _on(mutation, repo_root)
    else:
        result = _off(mutation, repo_root)

    # _on returns 3-tuple on success, 4-tuple on failure; normalize.
    if result[0]:
        # Inv 1 v0.7.4 (#377): emit branded rabbit_print confirmation lines
        # to stdout so the message matches the visual weight of the rest of
        # the rabbit surface (SessionStart banner, configurable alerts).
        # The SKILL.md `on`/`off` subcommand bodies surface this stdout
        # verbatim — the message text lives here so it stays centralized.
        rabbit_print = _import_rabbit_print()
        if action == "on":
            print(rabbit_print(
                "AUTONOMOUS-EVOLVE MODE CONFIGURED — restart Claude Code to activate",
                "\U0001f680", "red"))
            print(rabbit_print(
                "After restart, run: /rabbit-auto-evolve start",
                "\U0001f449", "yellow"))
        else:
            print(rabbit_print(
                "Autonomous-evolve mode deactivated — full teardown complete",
                "✅", "green"))
        sys.exit(0)
    _ok, failed_label, err, completed = result
    sys.stderr.write(f"set-evolve-mode: {action} failed at {failed_label}: {err}\n")
    rollback_failures = _rollback(completed)
    if rollback_failures:
        for line in rollback_failures:
            sys.stderr.write(f"set-evolve-mode: {line}\n")
    else:
        sys.stderr.write("set-evolve-mode: rollback succeeded\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
