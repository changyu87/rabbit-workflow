#!/usr/bin/env python3
"""prompt-injector.py — PreToolUse hook source for skill prompt injection (Inv 55).

This is the SOURCE artifact owned by the contract feature. Deployment to
.claude/hooks/ and the publish_hook manifest entry land in a later sub-cycle.
Until then this file is quiescent (does not fire on real Skill calls).

Behaviour:
  - Reads PreToolUse JSON from stdin: {"tool_name": ..., "tool_input": {...}}.
  - If tool_name != "Skill": emits {} to stdout, exit 0 (silent no-op).
  - If tool_name == "Skill":
      Walks .claude/features/*/feature.json looking for a `prompts` entry
      with kind=="skill" and id == tool_input.skill.
      - Not found: emits {} to stdout, exit 0 (silent no-op).
      - Found: invokes scripts/build-prompt.py via subprocess with
        --callable-id <id> --slot args=<value>, reads the resulting prompt
        file, and emits:
          {"hookSpecificOutput":
              {"hookEventName": "PreToolUse",
               "additionalContext": "<file contents>"}}
  - On any failure (assembler error, missing template, timeout, ...):
      Append a JSON line {ts, skill, callable_id, error} to
      <repo>/.rabbit/prompts/.injection-failures.log and emit {} silently
      (exit 0). The hook is best-effort and MUST NEVER block the user.
  - If the matched entry declares slots other than `args` (misconfiguration
    for kind="skill"), log a warning and skip injection without blocking.

Repo root is resolved from $RABBIT_ROOT (test harness override) or
`git rev-parse --show-toplevel` rooted at this script's directory.

Exit: always 0 (best-effort).

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when Claude Code exposes a native prompt-injection
    mechanism that replaces this hook.
"""

import json
import os
import subprocess
import sys
import time


def get_repo_root():
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(
            ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def log_failure(repo_root, skill, callable_id, error):
    """Append a JSON line to .rabbit/prompts/.injection-failures.log. Never raises."""
    try:
        log_dir = os.path.join(repo_root, ".rabbit", "prompts")
        os.makedirs(log_dir, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "skill": skill,
            "callable_id": callable_id,
            "error": str(error),
        }
        with open(os.path.join(log_dir, ".injection-failures.log"), "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def find_skill_entry(repo_root, skill_id):
    """Return (entry, feature_name) or (None, None)."""
    features_root = os.path.join(repo_root, ".claude", "features")
    if not os.path.isdir(features_root):
        return None, None
    try:
        entries = sorted(os.listdir(features_root))
    except OSError:
        return None, None
    for feat_name in entries:
        fjson = os.path.join(features_root, feat_name, "feature.json")
        if not os.path.isfile(fjson):
            continue
        try:
            with open(fjson) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        prompts = data.get("prompts")
        if not isinstance(prompts, list):
            continue
        for entry in prompts:
            if not isinstance(entry, dict):
                continue
            if entry.get("kind") == "skill" and entry.get("id") == skill_id:
                return entry, feat_name
    return None, None


def emit_silent():
    sys.stdout.write("{}")
    sys.stdout.flush()
    sys.exit(0)


def emit_additional_context(content):
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": content,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    sys.exit(0)


def main():
    # Read stdin event JSON.
    try:
        raw = sys.stdin.read()
    except Exception:
        emit_silent()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        emit_silent()

    tool_name = event.get("tool_name")
    if tool_name != "Skill":
        emit_silent()

    tool_input = event.get("tool_input") or {}
    skill_id = tool_input.get("skill")
    if not isinstance(skill_id, str) or not skill_id:
        emit_silent()

    repo_root = get_repo_root()
    if not repo_root:
        emit_silent()

    try:
        entry, _feat_name = find_skill_entry(repo_root, skill_id)
    except Exception as e:
        log_failure(repo_root, skill_id, None, f"lookup failed: {e}")
        emit_silent()

    if entry is None:
        # Unregistered skill: silent no-op.
        emit_silent()

    callable_id = entry.get("id")
    declared_slots = entry.get("slots") or []

    # Skill-kind entries must declare exactly one slot named "args".
    if declared_slots and declared_slots != ["args"]:
        log_failure(repo_root, skill_id, callable_id,
                    f"skill-kind entry has unexpected slots: {declared_slots} "
                    f"(only ['args'] is supported)")
        emit_silent()

    args_value = tool_input.get("args", "")
    if not isinstance(args_value, str):
        args_value = json.dumps(args_value)

    build_prompt = os.path.join(
        repo_root, ".claude", "features", "contract",
        "scripts", "build-prompt.py",
    )

    cmd = ["python3", build_prompt, "--callable-id", callable_id]
    if declared_slots == ["args"]:
        cmd += ["--slot", f"args={args_value}"]
    # else: entry declares no slots; pass none.

    env = dict(os.environ)
    env["RABBIT_ROOT"] = repo_root

    try:
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, env=env, timeout=10,
        )
    except subprocess.TimeoutExpired:
        log_failure(repo_root, skill_id, callable_id, "build-prompt.py timed out after 10s")
        emit_silent()
    except Exception as e:
        log_failure(repo_root, skill_id, callable_id, f"subprocess error: {e}")
        emit_silent()

    if r.returncode != 0:
        log_failure(repo_root, skill_id, callable_id,
                    f"build-prompt.py exit={r.returncode}; stderr={r.stderr.strip()}")
        emit_silent()

    out_path = r.stdout.strip()
    if not out_path or not os.path.isfile(out_path):
        log_failure(repo_root, skill_id, callable_id,
                    f"build-prompt.py did not write a file; stdout={out_path!r}")
        emit_silent()

    try:
        with open(out_path) as f:
            content = f.read()
    except OSError as e:
        log_failure(repo_root, skill_id, callable_id, f"cannot read assembled prompt: {e}")
        emit_silent()

    emit_additional_context(content)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Best-effort safety net.
        try:
            sys.stdout.write("{}")
            sys.stdout.flush()
        except Exception:
            pass
        sys.exit(0)
