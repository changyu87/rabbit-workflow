#!/usr/bin/env python3
"""update-state.py — validate and atomically persist auto-evolve loop state.

Usage:
  cat new-state.json | update-state.py

Per rabbit-auto-evolve spec.md Inv 9, reads a JSON state object from stdin,
validates it against scripts/schemas/auto-evolve-state.schema.json, and
writes the validated state to <state_dir>/auto-evolve-state.json atomically
via temp+rename.

  state_dir defaults to <cwd>/.rabbit
  state_dir is overridable via RABBIT_AUTO_EVOLVE_STATE_DIR env var (tests).

`restart_needed` is string|null (resolved Open Question 3). Pure booleans
are rejected with a type-mismatch detail in stderr.

Exit code: 0 on successful write; non-zero on schema-validation failure or
write error. On validation failure the state file is NOT touched.

Version: 1.1.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "schemas", "auto-evolve-state.schema.json")

UPDATED_AT_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


def _is_int(value):
    """True if value is an int but NOT a bool. (bool is a subclass of int.)"""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str_or_none(value):
    return value is None or isinstance(value, str)


def validate(instance):
    """Inline minimal validator covering the Inv 9 schema. Returns a list of
    human-readable error strings (empty list = valid). Each message names
    the offending field so test assertions can grep for the field name."""
    errors = []

    if not isinstance(instance, dict):
        return ["root: expected object, got " + type(instance).__name__]

    required = [
        "schema_version",
        "updated_at",
        "queue",
        "in_flight",
        "last_merged_sha",
        "last_tagged_version",
        "consecutive_failures",
        "stop_requested",
        "restart_needed",
    ]
    for field in required:
        if field not in instance:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    # additionalProperties: false, except the optional `defer_counts` map
    # (issue #423 Part B, schema 1.1.0).
    optional = {"defer_counts"}
    extra = set(instance.keys()) - set(required) - optional
    if extra:
        errors.append(
            "additional properties not allowed: " + ", ".join(sorted(extra))
        )

    if instance["schema_version"] != "1.1.0":
        errors.append(
            f"schema_version: expected '1.1.0', got {instance['schema_version']!r}"
        )

    updated_at = instance["updated_at"]
    if not isinstance(updated_at, str) or not UPDATED_AT_RE.match(updated_at):
        errors.append(
            f"updated_at: expected ISO-8601 UTC 'YYYY-MM-DDTHH:MM:SSZ', got {updated_at!r}"
        )

    queue = instance["queue"]
    if not isinstance(queue, list):
        errors.append(f"queue: expected array, got {type(queue).__name__}")
    else:
        for i, item in enumerate(queue):
            if not isinstance(item, dict):
                errors.append(f"queue[{i}]: expected object, got {type(item).__name__}")
                continue
            for k, want_int in (("issue", True), ("decision", False), ("feature", False)):
                if k not in item:
                    errors.append(f"queue[{i}]: missing required field: {k}")
                    continue
                v = item[k]
                if want_int and not _is_int(v):
                    errors.append(f"queue[{i}].{k}: expected integer, got {type(v).__name__}")
                if not want_int and not isinstance(v, str):
                    errors.append(f"queue[{i}].{k}: expected string, got {type(v).__name__}")

    in_flight = instance["in_flight"]
    if not isinstance(in_flight, list):
        errors.append(f"in_flight: expected array, got {type(in_flight).__name__}")
    else:
        for i, n in enumerate(in_flight):
            if not _is_int(n):
                errors.append(f"in_flight[{i}]: expected integer, got {type(n).__name__}")

    if not _is_str_or_none(instance["last_merged_sha"]):
        errors.append(
            f"last_merged_sha: expected string|null, got {type(instance['last_merged_sha']).__name__}"
        )
    if not _is_str_or_none(instance["last_tagged_version"]):
        errors.append(
            f"last_tagged_version: expected string|null, got {type(instance['last_tagged_version']).__name__}"
        )

    cf = instance["consecutive_failures"]
    if not _is_int(cf):
        errors.append(f"consecutive_failures: expected integer, got {type(cf).__name__}")
    elif cf < 0:
        errors.append(f"consecutive_failures: expected >= 0, got {cf}")

    if not isinstance(instance["stop_requested"], bool):
        errors.append(
            f"stop_requested: expected boolean, got {type(instance['stop_requested']).__name__}"
        )

    # restart_needed: string|null. Bool and int are explicitly rejected.
    rn = instance["restart_needed"]
    if not _is_str_or_none(rn):
        errors.append(
            f"restart_needed: expected string|null, got {type(rn).__name__}"
        )

    # defer_counts (optional): object of issue-number-string → non-negative
    # int (issue #423 Part B).
    if "defer_counts" in instance:
        dc = instance["defer_counts"]
        if not isinstance(dc, dict):
            errors.append(
                f"defer_counts: expected object, got {type(dc).__name__}"
            )
        else:
            for k, v in dc.items():
                if not _is_int(v):
                    errors.append(
                        f"defer_counts[{k!r}]: expected integer, got "
                        f"{type(v).__name__}"
                    )
                elif v < 0:
                    errors.append(
                        f"defer_counts[{k!r}]: expected >= 0, got {v}"
                    )

    return errors


def _resolve_state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def main():
    parser = argparse.ArgumentParser(
        description="Validate auto-evolve loop state JSON read on stdin and "
                    "atomically persist to .rabbit/auto-evolve-state.json. "
                    "Honors RABBIT_AUTO_EVOLVE_STATE_DIR env override."
    )
    parser.parse_args()

    raw = sys.stdin.read()
    try:
        instance = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"update-state: stdin is not valid JSON: {e}\n")
        sys.exit(1)

    errors = validate(instance)
    if errors:
        for err in errors:
            sys.stderr.write(f"update-state: validation error: {err}\n")
        sys.exit(1)

    state_dir = _resolve_state_dir()
    os.makedirs(state_dir, exist_ok=True)
    tmp_path = os.path.join(state_dir, "auto-evolve-state.json.tmp")
    final_path = os.path.join(state_dir, "auto-evolve-state.json")

    try:
        with open(tmp_path, "w") as f:
            json.dump(instance, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, final_path)
    except OSError as e:
        sys.stderr.write(f"update-state: write failed: {e}\n")
        # best-effort cleanup of tmp
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
