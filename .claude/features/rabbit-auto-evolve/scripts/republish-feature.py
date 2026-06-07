#!/usr/bin/env python3
"""republish-feature.py — re-deploy a feature's surfaces from its manifest.

Per rabbit-auto-evolve spec.md Inv 55 (issue #562). A version-bumping TDD
subagent bumps a feature's SOURCE SKILL.md (required for four-way version
equality) but CANNOT write the deployed `.claude/skills/<feature>/SKILL.md`
copy — that path is outside the subagent's `.rabbit-scope-active-<feature>`
scope, so the scope guard denies the write. Left unrepublished, the deployed
copy lags source and `contract/test/test-deployed-skills-match-source.py` is
RED on every version-bumping touch.

This script makes the republish a deterministic, repeatable DISPATCHER step.
Given a feature name (and optional `--repo-root`, default cwd), it reads that
feature's `feature.json` `manifest` and runs each deploy entry by INVOKING
`contract.lib.publish.<api>(**args, feature_dir=..., repo_root=...)` for every
`publish_skill` / `publish_hook` / `publish_file` / `publish_command` /
`publish_*` entry — exactly what the dispatcher otherwise does by hand. This
is a cross-scope INVOKE of the contract-owned publish API declared in this
feature's `contract.md` `invokes.modules`; rabbit-auto-evolve never edits the
contract feature.

Idempotent: the contract publish APIs are no-ops when the deployed copy
already matches source (by SHA-256). A feature with no `manifest` / no publish
entries is a clean no-op.

Emits a single JSON object on stdout:

  {
    "feature": "rabbit-foo",
    "published": [
      {"api": "publish_skill", "args": {...},
       "changed": true, "message": "OK: .claude/skills/... published"}
    ],
    "status": "ok"
  }

`status` is "error" (and exit 1) when feature.json is missing/unparseable, the
contract publish lib cannot be resolved, or any publish call returns
passed=False. Otherwise exit 0.

`contract.lib.publish` is resolved by inserting the sibling `contract`
feature dir onto `sys.path` and importing `from lib import publish` — the
established cross-scope import pattern used by `prune-worktrees.py`. The
contract dir is resolved from `<repo_root>/.claude/features/contract` when
present (the canonical location), else relative to this script's own dirname
(`scripts/ -> rabbit-auto-evolve/ -> features/ -> contract`), so the import
works in both the worktree/dev tree and a deployed install.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _repo_root(arg_root: str | None) -> str:
    return arg_root or os.getcwd()


def _feature_dir(repo_root: str, feature: str) -> str:
    return os.path.join(repo_root, ".claude", "features", feature)


def _resolve_contract_dir(repo_root: str) -> str:
    """Locate the `contract` feature dir for the publish lib import.

    Prefer `<repo_root>/.claude/features/contract` (canonical, and what the
    fixture repos vendor); fall back to this script's own sibling contract dir
    (scripts/ -> rabbit-auto-evolve/ -> features/ -> contract) so the import
    works in a deployed install where cwd may differ.
    """
    candidate = os.path.join(repo_root, ".claude", "features", "contract")
    if os.path.isdir(os.path.join(candidate, "lib")):
        return candidate
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "contract"))


def _import_publish(repo_root: str):
    """Import the contract-owned publish module (cross-scope INVOKE).

    Mirrors prune-worktrees.py's lazy contract-lib import: insert the contract
    feature dir onto sys.path, then `from lib import publish`.
    """
    contract_dir = _resolve_contract_dir(repo_root)
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    from lib import publish  # noqa: PLC0415
    return publish


def _load_manifest(feature_dir: str):
    """Return the feature's manifest list (possibly empty).

    Raises FileNotFoundError / ValueError for a missing / unparseable
    feature.json so the caller can report status=error.
    """
    fj_path = os.path.join(feature_dir, "feature.json")
    with open(fj_path) as f:
        data = json.load(f)
    manifest = data.get("manifest", [])
    if not isinstance(manifest, list):
        raise ValueError("feature.json 'manifest' is not a list")
    return manifest


def republish(feature: str, repo_root: str) -> dict:
    """Run every publish_* manifest entry; return the summary dict."""
    feature_dir = _feature_dir(repo_root, feature)
    result = {"feature": feature, "published": [], "status": "ok"}

    try:
        manifest = _load_manifest(feature_dir)
    except (OSError, ValueError) as e:
        result["status"] = "error"
        result["error"] = f"cannot read feature.json: {e}"
        return result

    if not manifest:
        # No manifest / no publish entries — clean no-op.
        return result

    try:
        publish = _import_publish(repo_root)
    except ImportError as e:
        result["status"] = "error"
        result["error"] = f"cannot import contract.lib.publish: {e}"
        return result

    for entry in manifest:
        api = entry.get("api", "")
        args = entry.get("args", {}) or {}
        if not api.startswith("publish_"):
            result["status"] = "error"
            result["error"] = f"manifest entry api is not a publish_* call: {api!r}"
            return result
        fn = getattr(publish, api, None)
        if fn is None:
            result["status"] = "error"
            result["error"] = f"contract.lib.publish has no API {api!r}"
            return result
        try:
            check = fn(**args, feature_dir=feature_dir, repo_root=repo_root)
        except TypeError as e:
            result["status"] = "error"
            result["error"] = f"{api} args mismatch: {e}"
            return result
        messages = list(getattr(check, "messages", []) or [])
        message = messages[-1] if messages else ""
        # The contract publish APIs append "no-op" to the message when the
        # destination already matched source; anything else is a real write.
        changed = check.passed and "no-op" not in message.lower()
        result["published"].append({
            "api": api,
            "args": args,
            "changed": changed,
            "message": message,
        })
        if not check.passed:
            result["status"] = "error"
            result["error"] = f"{api} failed: {message}"
            return result

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-deploy a feature's surfaces from its feature.json "
                    "manifest by invoking contract.lib.publish.<api> for every "
                    "publish_* entry. Idempotent; emits a JSON summary on "
                    "stdout. Exit 1 on error, 0 otherwise."
    )
    parser.add_argument("feature", help="feature name (dir under .claude/features/)")
    parser.add_argument(
        "--repo-root", default=None,
        help="repo root containing .claude/features/ (default: cwd)",
    )
    args = parser.parse_args()

    result = republish(args.feature, _repo_root(args.repo_root))
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
