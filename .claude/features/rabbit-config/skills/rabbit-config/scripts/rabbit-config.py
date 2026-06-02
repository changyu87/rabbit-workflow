#!/usr/bin/env python3
"""rabbit-config.py — /rabbit-config skill interpreter.

Enumerates every feature's CONFIGURATION declarations, finds the entry whose
subcommand matches argv[1], and dispatches to contract.lib.mutation.

Usage: rabbit-config.py <subcommand> [<value-or-action> [<template-value>]]

  Values-style:  rabbit-config <subcommand> <value>
  Actions-style: rabbit-config <subcommand> <action> [<template-value>]

Version: 1.3.0
Owner: rabbit-workflow team (rabbit-config)
Deprecation criterion: when the rabbit CLI exposes native configuration mutation.
"""

import json
import os
import re
import sys


def _repo_root():
    return os.getcwd()


def _enumerate_configurations(repo_root):
    """Yield (feature_name, feature_dir, cfg_entry) for each CONFIGURATION entry,
    alphabetically by feature name, in declaration order within each feature.
    Skips retired features and features with malformed or missing feature.json.
    """
    features_root = os.path.join(repo_root, ".claude", "features")
    if not os.path.isdir(features_root):
        return
    for name in sorted(os.listdir(features_root)):
        fdir = os.path.join(features_root, name)
        fj = os.path.join(fdir, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("status") == "retired":
            continue
        configuration = data.get("configuration")
        if not isinstance(configuration, list):
            continue
        for cfg in configuration:
            if isinstance(cfg, dict):
                yield name, fdir, cfg


def _has_templates(obj):
    """Return True if any string value in obj (dict or list) contains {placeholder}."""
    pattern = re.compile(r'\{[a-z_]+\}')
    if isinstance(obj, dict):
        for v in obj.values():
            if _has_templates(v):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _has_templates(item):
                return True
    elif isinstance(obj, str):
        return bool(pattern.search(obj))
    return False


def _apply_template(obj, value):
    """Replace {tool}, {command}, and {value} placeholders with value; returns new obj."""
    if isinstance(obj, dict):
        return {k: _apply_template(v, value) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_template(item, value) for item in obj]
    if isinstance(obj, str):
        return (obj.replace("{tool}", value)
                   .replace("{command}", value)
                   .replace("{value}", value))
    return obj


def _validate(validation, user_value, subcommand):
    """Apply validation rules to user_value. Return error message or None."""
    if not validation:
        return None
    reject_prefix = validation.get("reject_prefix")
    if reject_prefix and user_value.startswith(reject_prefix):
        return (f"rabbit-config {subcommand}: value must not start with "
                f"'{reject_prefix}' (use bash-allow for Bash commands)")
    reject_chars = validation.get("reject_chars")
    if reject_chars:
        if re.search(f"[{reject_chars}]", user_value):
            return (f"rabbit-config {subcommand}: value contains a forbidden "
                    f"character (reject pattern: {reject_chars!r})")
    return None


def main():
    repo_root = _repo_root()
    contract_dir = os.path.join(repo_root, ".claude", "features", "contract")
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    try:
        from lib import mutation  # noqa: PLC0415
    except ImportError as e:
        sys.stderr.write(f"rabbit-config: cannot import contract.lib.mutation: {e}\n")
        sys.exit(1)

    all_configs = list(_enumerate_configurations(repo_root))
    argv = sys.argv[1:]

    if not argv:
        subcommands = sorted({cfg.get("subcommand", "") for _, _, cfg in all_configs
                               if cfg.get("subcommand")})
        sys.stderr.write("Usage: rabbit-config <subcommand> [<value-or-action> [<template-value>]]\n")
        sys.stderr.write(f"Known subcommands: {', '.join(subcommands)}\n")
        sys.exit(1)

    subcommand = argv[0]
    matches = [(fname, fdir, cfg) for fname, fdir, cfg in all_configs
               if cfg.get("subcommand") == subcommand]

    if not matches:
        subcommands = sorted({cfg.get("subcommand", "") for _, _, cfg in all_configs
                               if cfg.get("subcommand")})
        sys.stderr.write(f"rabbit-config: unknown subcommand '{subcommand}'\n")
        sys.stderr.write(f"Known subcommands: {', '.join(subcommands)}\n")
        sys.exit(1)

    _, feature_dir, cfg = matches[0]
    values = cfg.get("values")
    actions = cfg.get("actions")
    validation = cfg.get("validation")

    if values is not None:
        if len(argv) < 2:
            sys.stderr.write(f"rabbit-config {subcommand}: requires a value\n")
            sys.stderr.write(f"Valid values: {', '.join(sorted(values.keys()))}\n")
            sys.exit(1)
        user_value = argv[1]
        err = _validate(validation, user_value, subcommand)
        if err:
            sys.stderr.write(f"{err}\n")
            sys.exit(1)
        if user_value not in values:
            sys.stderr.write(f"rabbit-config {subcommand}: unknown value '{user_value}'\n")
            sys.stderr.write(f"Valid values: {', '.join(sorted(values.keys()))}\n")
            sys.exit(1)
        api_call = values[user_value]
        api_name = api_call["api"]
        api_args = dict(api_call.get("args") or {})

    elif actions is not None:
        if len(argv) < 2:
            sys.stderr.write(f"rabbit-config {subcommand}: requires an action\n")
            sys.stderr.write(f"Valid actions: {', '.join(sorted(actions.keys()))}\n")
            sys.exit(1)
        action = argv[1]
        if action not in actions:
            sys.stderr.write(f"rabbit-config {subcommand}: unknown action '{action}'\n")
            sys.stderr.write(f"Valid actions: {', '.join(sorted(actions.keys()))}\n")
            sys.exit(1)
        api_call = actions[action]
        api_name = api_call["api"]
        api_args = dict(api_call.get("args") or {})

        if _has_templates(api_args):
            if len(argv) < 3:
                sys.stderr.write(
                    f"rabbit-config {subcommand} {action}: requires a value argument\n")
                sys.exit(1)
            template_value = argv[2]
            err = _validate(validation, template_value, subcommand)
            if err:
                sys.stderr.write(f"{err}\n")
                sys.exit(1)
            api_args = _apply_template(api_args, template_value)

    else:
        sys.stderr.write(
            f"rabbit-config {subcommand}: this configurable has no values or actions\n")
        sys.exit(1)

    fn = getattr(mutation, api_name, None)
    if fn is None:
        sys.stderr.write(f"rabbit-config: unknown mutation API '{api_name}'\n")
        sys.exit(1)

    if api_name == "run_feature_script":
        result = fn(**api_args, feature_dir=feature_dir)
    else:
        result = fn(**api_args, repo_root=repo_root)

    for msg in (getattr(result, "messages", None) or []):
        print(msg)

    if not getattr(result, "passed", False):
        sys.exit(1)

    # Inv 20: configurables whose effect is read only at Claude Code process
    # start (e.g. permissions.defaultMode) declare restart_required: true in
    # their feature.json configuration[] entry. After a successful mutation,
    # emit one yellow rabbit_subline-style alert telling the user to relaunch
    # Claude — without it, the mutation silently succeeds but the new mode
    # does not take effect until the next session boot.
    if cfg.get("restart_required"):
        scripts_dir = os.path.join(repo_root, ".claude", "features",
                                   "contract", "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from rabbit_print import rabbit_subline  # noqa: PLC0415
        print(rabbit_subline(
            f"restart Claude (exit + relaunch) for the new {subcommand} "
            "value to take effect",
            color="yellow",
        ))


if __name__ == "__main__":
    main()
