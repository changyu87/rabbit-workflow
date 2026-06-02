#!/usr/bin/env python3
"""install.py — install rabbit as a plugin at <project>/.rabbit/ + dev-test helper.

This module has two distinct roles:

  1. User-facing MVP installer (main()):
     Invoked by install.sh after the upstream tarball is extracted. Lays
     down the minimum file closure needed for the user-promised surfaces:

       1. Drift-protected Claude on session start (policy block via CLAUDE.md)
       2. rabbit-feature-scaffold <name> <path-glob> (declare a feature mapping)
       3. Scope-guard blocking edits to declared-feature paths
       4. .rabbit/.runtime/scope-bypass-once one-shot override marker

     Each (source, dest) tuple at module top is explicit so the installer
     doesn't depend on the publish flow having been run against the source
     tarball.

     Excludes development surfaces: test/, docs/, scripts/enforcement/,
     deferred features (tdd-subagent), retired
     tombstones (tdd-state-machine).

     Usage:
         install.py --src <extracted-tarball-dir> --target <project>/.rabbit
         install.py --update    (self-fetch upstream; infer target from script
                                 location — see Inv 22g)

  2. Dev-test helper (run_publish_loop()):
     Importable function used by rabbit-cage test suites
     (test-deployed-hooks-execute.py, test-install-publish-loop.py) to
     exercise the publish flow against a freshly copied .claude tree.
     This helper is NOT invoked from main() — main() lays down an explicit
     file closure rather than running the publish flow at install time.

Version: 6.4.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit's per-project plugin model is superseded
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# Inv 29: hardcoded stable-release default for --update self-fetch when neither
# --version/--ref CLI flag, --channel dev, nor RABBIT_REF env var is supplied.
# MUST match install.sh's RABBIT_REF="${RABBIT_REF:-…}" default — single source
# of truth, bumped together each release cut. The literal value "dev" is
# FORBIDDEN here (enforced by test-install-py-default-ref-not-dev.py).
HARDCODED_STABLE_DEFAULT = "release/1.5"

# ───────────────────────────────────────────────────────────────────────────
# MVP file closure as (src_rel, dst_rel) tuples — explicit source→destination
# ───────────────────────────────────────────────────────────────────────────

# Top-level files (same path on both sides)
SAME_PATH_FILES = [
    "CLAUDE.md",
    "README.md",
    "install.py",
    ".claude/settings.json",
]

# Hooks: source → deployed
HOOKS = [
    (".claude/features/rabbit-cage/hooks/scope-guard.py", ".claude/hooks/scope-guard.py"),
    (".claude/features/rabbit-cage/hooks/session-start-dispatcher.py", ".claude/hooks/session-start-dispatcher.py"),
    (".claude/features/rabbit-cage/hooks/stop-dispatcher.py", ".claude/hooks/stop-dispatcher.py"),
    (".claude/features/rabbit-cage/hooks/user-prompt-submit-dispatcher.py", ".claude/hooks/user-prompt-submit-dispatcher.py"),
    (".claude/features/rabbit-cage/hooks/_dispatcher_lib.py", ".claude/hooks/_dispatcher_lib.py"),
    (".claude/features/contract/hooks/prompt-injector.py", ".claude/hooks/prompt-injector.py"),
]

# Skills: source SKILL.md → deployed SKILL.md
SKILLS = [
    (".claude/features/rabbit-feature/skills/rabbit-feature-scaffold/SKILL.md", ".claude/skills/rabbit-feature-scaffold/SKILL.md"),
    (".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md", ".claude/skills/rabbit-feature-touch/SKILL.md"),
    (".claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md", ".claude/skills/rabbit-feature-scope/SKILL.md"),
    (".claude/features/rabbit-feature/skills/rabbit-feature-audit/SKILL.md", ".claude/skills/rabbit-feature-audit/SKILL.md"),
    (".claude/features/rabbit-config/skills/rabbit-config/SKILL.md", ".claude/skills/rabbit-config/SKILL.md"),
    (".claude/features/rabbit-issue/skills/rabbit-issue/SKILL.md", ".claude/skills/rabbit-issue/SKILL.md"),
    (".claude/features/rabbit-spec/skills/rabbit-spec-create/SKILL.md", ".claude/skills/rabbit-spec-create/SKILL.md"),
    (".claude/features/rabbit-spec/skills/rabbit-spec-update/SKILL.md", ".claude/skills/rabbit-spec-update/SKILL.md"),
    (".claude/features/rabbit-decompose/skills/rabbit-decompose/SKILL.md", ".claude/skills/rabbit-decompose/SKILL.md"),
]

# Agents: source → deployed
AGENTS = [
    (".claude/features/rabbit-spec/agents/spec-creator.md", ".claude/agents/spec-creator.md"),
    (".claude/features/tdd-subagent/agents/tdd-subagent.md", ".claude/agents/tdd-subagent.md"),
]

# Commands: source → deployed
COMMANDS: list[tuple[str, str]] = [
    (".claude/features/rabbit-cage/commands/rabbit-refresh.md", ".claude/commands/rabbit-refresh.md"),
    (".claude/features/rabbit-cage/commands/rabbit-project.md", ".claude/commands/rabbit-project.md"),
]

# Per-feature sub-path includes (whole subset; same path on both sides)
FEATURE_INCLUDES: dict[str, list[str]] = {
    "contract": [
        "feature.json",
        "hooks/prompt-injector.py",
        "lib/__init__.py",
        "lib/runtime.py",
        "lib/checks.py",
        "lib/policy_block.py",
        "lib/mutation.py",
        "lib/producers.py",
        "lib/publish.py",
        "scripts/build-prompt.py",
        "scripts/rabbit_print.py",
        "scripts/validate-feature.py",
        "scripts/validate-meta-contract.py",
        "scripts/find-feature.py",
        "scripts/policy-block.py",
        "schemas/feature.json.schema.json",
        "schemas/runtime.schema.json",
        "schemas/prompts.schema.json",
        "schemas/project-map.json.schema.json",
        "schemas/manifest.schema.json",
        "schemas/rabbit-print.schema.json",
        "templates/spec-template.md",
        "templates/contract-template.md",
        "templates/feature-json-template.json",
        "templates/project-map-template.json",
        "templates/prompts/rabbit-config.txt",
        "templates/prompts/rabbit-decompose.txt",
        "templates/prompts/rabbit-feature-audit.txt",
        "templates/prompts/rabbit-feature-scaffold.txt",
        "templates/prompts/rabbit-feature-scope.txt",
        "templates/prompts/rabbit-feature-touch.txt",
        "templates/prompts/rabbit-issue.txt",
        "templates/prompts/rabbit-spec-update.txt",
        "templates/prompts/spec-create.txt",
        "templates/prompts/tdd-subagent.txt",
    ],
    "policy": [
        "feature.json",
        "philosophy.md",
        "spec-rules.md",
        "coding-rules.md",
    ],
    "rabbit-cage": [
        "feature.json",
        "settings.json",
        "README.md",
        "install.py",
        "policy-header.json",
        "hooks/scope-guard.py",
        "hooks/stop-dispatcher.py",
        "hooks/session-start-dispatcher.py",
        "hooks/user-prompt-submit-dispatcher.py",
        "hooks/_dispatcher_lib.py",
        "commands/rabbit-refresh.md",
        "commands/rabbit-project.md",
        "lib/__init__.py",
        "lib/project_map_reader.py",
    ],
    "rabbit-meta": [
        "feature.json",
        "lib/__init__.py",
        "lib/mode_detection.py",
        "lib/generate_claude_md.py",
        "lib/generate_readme.py",
        "templates/CLAUDE.md.template",
        "templates/README.md.template",
    ],
    "rabbit-feature": [
        "feature.json",
        "scripts/format-feature-context.py",
        "scripts/resolve-scope.py",
        "scripts/scaffold-feature.py",
        "skills/rabbit-feature-audit/SKILL.md",
        "skills/rabbit-feature-scaffold/SKILL.md",
        "skills/rabbit-feature-scope/SKILL.md",
        "skills/rabbit-feature-touch/SKILL.md",
    ],
    "rabbit-config": [
        "feature.json",
        "skills/rabbit-config/SKILL.md",
        "skills/rabbit-config/scripts/rabbit-config.py",
    ],
    "rabbit-issue": [
        "feature.json",
        "skills/rabbit-issue/SKILL.md",
        "scripts/_gh.py",
        "scripts/file-item.py",
        "scripts/item-status.py",
        "scripts/list-items.py",
    ],
    "rabbit-spec": [
        "feature.json",
        "agents/spec-creator.md",
        "scripts/dispatch-spec-create.py",
        "skills/rabbit-spec-create/SKILL.md",
        "skills/rabbit-spec-update/SKILL.md",
    ],
    "rabbit-decompose": [
        "feature.json",
        "skills/rabbit-decompose/SKILL.md",
    ],
    "tdd-subagent": [
        "feature.json",
        "agents/tdd-subagent.md",
        "scripts/dispatch-tdd-subagent.py",
        "scripts/tdd-step.py",
    ],
}


def copy_one(src_root: Path, dst_root: Path, src_rel: str, dst_rel: str) -> bool:
    src = src_root / src_rel
    dst = dst_root / dst_rel
    if not src.is_file():
        print(f"error: missing required source file: {src_rel}", file=sys.stderr)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    # Preserve executable bit for shell + python scripts copied to user-runnable locations
    if dst.suffix in (".py", ".sh") or "scripts/" in dst_rel or "hooks/" in dst_rel:
        os.chmod(dst, os.stat(dst).st_mode | 0o111)
    return True


def _rewrite_one(path: Path, rabbit_root: str) -> None:
    """Apply the two Inv 19 edits in place to a single settings.json file.

    (a) Sets env.RABBIT_ROOT to `rabbit_root`; creates the env block if
        absent; overwrites any existing RABBIT_ROOT key.
    (b) Replaces every literal '$(git rev-parse --show-toplevel)' occurrence
        with '$RABBIT_ROOT' inside any hooks[<event>][].hooks[].command
        string. No other fields touched.

    Idempotent: re-running on an already-rewritten file is a no-op.
    """
    with open(path) as f:
        data = json.load(f)

    env_block = data.get("env")
    if not isinstance(env_block, dict):
        env_block = {}
        data["env"] = env_block
    env_block["RABBIT_ROOT"] = rabbit_root

    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for _event, entries in hooks.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                inner = entry.get("hooks")
                if not isinstance(inner, list):
                    continue
                for h in inner:
                    if not isinstance(h, dict):
                        continue
                    cmd = h.get("command")
                    if isinstance(cmd, str):
                        h["command"] = cmd.replace(
                            "$(git rev-parse --show-toplevel)", "$RABBIT_ROOT"
                        )

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def rewrite_settings_for_plugin(dst_root: Path) -> None:
    """Inv 19: rewrite both the deployed settings.json and the feature-local
    source copy so that `check_manifest_drift` (which republishes from the
    source) produces a result identical to the deployed copy.

    Applies `_rewrite_one` to:
      - <dst_root>/.claude/settings.json (deployed copy)
      - <dst_root>/.claude/features/rabbit-cage/settings.json (source copy,
        guarded with `is_file()` — only present when the rabbit-cage feature
        directory was shipped in the install closure).

    Idempotent: re-running on already-rewritten files is a no-op.
    """
    rabbit_root = str(dst_root.resolve())
    deployed_settings = dst_root / ".claude/settings.json"
    if deployed_settings.is_file():
        _rewrite_one(deployed_settings, rabbit_root)
    source_settings = dst_root / ".claude/features/rabbit-cage/settings.json"
    if source_settings.is_file():
        _rewrite_one(source_settings, rabbit_root)


def write_rabbit_gitignore(dst_root: Path) -> None:
    content = (
        "# rabbit-owned ephemerals — never commit these\n"
        ".runtime/\n"
        "prompts/\n"
        "tdd-report-*.json\n"
        "impl-suggestion-*.json\n"
        ".scope-active-*\n"
        ".scope-bypass-once\n"
        "__pycache__/\n"
        "*.pyc\n"
    )
    (dst_root / ".gitignore").write_text(content)


def write_version_pin(dst_root: Path) -> None:
    label = os.environ.get("RABBIT_INSTALLED_REF", "unknown")
    (dst_root / ".version").write_text(label + "\n")


def fetch_upstream(repo: str, ref: str, dest: Path) -> Path:
    """Inv 22g: download the upstream tarball into `dest` and return the
    extracted `rabbit-workflow-*` dir.

    Uses stdlib urllib.request + tarfile only (Inv 4 Tech Stack). Raises on
    any failure (URLError / OSError / tarfile.ReadError / StopIteration);
    callers translate the exception into a clean exit 1.
    """
    url = f"https://github.com/{repo}/archive/{ref}.tar.gz"
    tarball = dest / "rabbit.tar.gz"
    with urllib.request.urlopen(url) as resp, open(tarball, "wb") as f:
        shutil.copyfileobj(resp, f)
    with tarfile.open(tarball) as tar:
        tar.extractall(dest)
    return next(
        p for p in dest.iterdir()
        if p.is_dir() and p.name.startswith("rabbit-workflow-")
    )


def run_publish_loop(target_root: str) -> int:
    """Dev-test helper: enumerate every <target_root>/.claude/features/*/feature.json
    and invoke each MANIFEST API via contract.lib.publish. Continues past
    failures; returns the count of failed calls (0 == success).

    Skips features with status == 'retired' and features with no manifest.
    Writes one stderr line per failure naming the feature + API.

    NOT invoked from main() — main() lays down an explicit file closure
    rather than executing the publish flow at install time. This function
    is retained as an importable helper for rabbit-cage test suites that
    exercise the publish flow against a freshly copied .claude tree
    (test-deployed-hooks-execute.py, test-install-publish-loop.py).
    """
    contract_dir = os.path.join(target_root, ".claude/features/contract")
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    try:
        from lib import publish  # noqa: PLC0415
    except ImportError as e:
        sys.stderr.write(f"install: cannot import contract.lib.publish: {e}\n")
        return 1

    features_root = os.path.join(target_root, ".claude/features")
    if not os.path.isdir(features_root):
        return 0

    failures = 0
    for name in sorted(os.listdir(features_root)):
        fdir = os.path.join(features_root, name)
        fj = os.path.join(fdir, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(f"install: {name}: malformed feature.json: {e}\n")
            failures += 1
            continue
        if not isinstance(data, dict) or data.get("status") == "retired":
            continue
        manifest = data.get("manifest") or []
        for entry in manifest:
            api_name = entry.get("api", "")
            args = entry.get("args") or {}
            fn = getattr(publish, api_name, None)
            if fn is None:
                sys.stderr.write(
                    f"install: {name}: unknown publish API {api_name!r}\n")
                failures += 1
                continue
            try:
                result = fn(**args, feature_dir=fdir, repo_root=target_root)
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(
                    f"install: {name}::{api_name} raised: {e}\n")
                failures += 1
                continue
            if not getattr(result, "passed", False):
                for msg in getattr(result, "messages", []) or []:
                    sys.stderr.write(f"install: {name}::{api_name}: {msg}\n")
                failures += 1
    return failures


def _publish_settings_merge(src_root: Path, dst_root: Path) -> bool:
    """Inv 22d: route the --update settings.json write through
    contract.lib.publish.publish_settings so non-rabbit hook entries,
    user-added permissions, and user-set env vars survive the refresh.

    The merge reads its source from the feature-local copy under
    <target>/.claude/features/rabbit-cage/settings.json — the closure copy
    that the per-feature refresh loop has already overwritten with the
    fresh upstream bytes. Returns True on success; False on any failure.
    """
    contract_dir = str(dst_root / ".claude/features/contract")
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    from lib import publish  # noqa: PLC0415

    feature_dir = str(dst_root / ".claude/features/rabbit-cage")
    result = publish.publish_settings(
        source="settings.json",
        feature_dir=feature_dir,
        repo_root=str(dst_root),
    )
    return bool(result.passed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install rabbit into a target directory")
    parser.add_argument("--src", required=False, default=None, type=Path,
                        help="extracted upstream source dir (optional under --update; self-fetched if omitted)")
    parser.add_argument("--target", required=False, default=None, type=Path,
                        help="target install dir (optional under --update; inferred from script location if omitted)")
    parser.add_argument("--update", action="store_true",
                        help="refresh an existing install in place (Inv 22)")
    # Inv 29: shell-agnostic ref-selection flags for --update self-fetch.
    # Precedence (highest wins): --version/--ref > --channel dev > RABBIT_REF env
    # > HARDCODED_STABLE_DEFAULT. Never silent 'dev'.
    parser.add_argument("--version", default=None,
                        help="upstream ref to install (branch, tag, or SHA); shell-agnostic alternative to RABBIT_REF env var")
    parser.add_argument("--ref", default=None,
                        help="alias for --version")
    parser.add_argument("--channel", default=None, choices=["stable", "dev"],
                        help="opt-in shorthand: 'dev' for bleeding-edge, 'stable' for hardcoded release default")
    args = parser.parse_args()

    # Inv 22g: --src and --target are optional under --update; outside --update
    # both remain required (matches the original argparse contract).
    if not args.update:
        missing = []
        if args.src is None:
            missing.append("--src")
        if args.target is None:
            missing.append("--target")
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))

    # Inv 22g: tempdir keeps the extracted upstream tarball alive for the
    # entire main() body when self-fetching. Always opened so the cleanup
    # path is uniform; only populated when fetching.
    fetch_tmp = tempfile.TemporaryDirectory()
    try:
        # Inv 22g (a): self-fetch when --update is set and --src is omitted.
        if args.update and args.src is None:
            repo = os.environ.get("RABBIT_REPO", "changyu87/rabbit-workflow")
            # Inv 29 precedence ladder. NEVER silent 'dev'.
            if args.version is not None:
                ref = args.version
            elif args.ref is not None:
                ref = args.ref
            elif args.channel == "dev":
                ref = "dev"
            elif "RABBIT_REF" in os.environ:
                ref = os.environ["RABBIT_REF"]
            else:
                ref = HARDCODED_STABLE_DEFAULT
            url = f"https://github.com/{repo}/archive/{ref}.tar.gz"
            try:
                fetched = fetch_upstream(repo, ref, Path(fetch_tmp.name))
            except Exception as e:  # noqa: BLE001 — surface root cause uniformly
                print(f"error: fetch failed: {url}: {e}", file=sys.stderr)
                return 1
            args.src = fetched
            # Inv 22e wiring: ensure .version reflects the fetched ref.
            if "RABBIT_INSTALLED_REF" not in os.environ:
                os.environ["RABBIT_INSTALLED_REF"] = ref

        # Inv 22g (b): infer --target from script location when --update is
        # set and --target is omitted. Sanity-check: must look like a rabbit
        # install root (.claude/ + .version present).
        if args.update and args.target is None:
            inferred = Path(__file__).resolve().parent
            if not (inferred / ".claude").exists() or not (inferred / ".version").exists():
                print(
                    f"error: --target inferred as {inferred} is not a rabbit "
                    f"install root (missing .claude/ or .version); pass --target explicitly",
                    file=sys.stderr,
                )
                return 1
            args.target = inferred

        return _main_with_args(args)
    finally:
        fetch_tmp.cleanup()


def _main_with_args(args: argparse.Namespace) -> int:
    src_root: Path = args.src.resolve()
    dst_root: Path = args.target.resolve()

    if not src_root.is_dir():
        print(f"error: --src is not a directory: {src_root}", file=sys.stderr)
        return 1
    if not args.update and dst_root.exists() and any(dst_root.iterdir()):
        print(f"error: --target exists and is not empty: {dst_root}", file=sys.stderr)
        return 1

    # Inv 22e: print version transition before any refresh so the operator
    # sees the pin movement even if a later copy fails partway through.
    if args.update:
        version_file = dst_root / ".version"
        if version_file.is_file():
            old_ref = version_file.read_text().strip()
            new_ref = os.environ.get("RABBIT_INSTALLED_REF", "unknown")
            print(f"updating {old_ref} -> {new_ref}")

    dst_root.mkdir(parents=True, exist_ok=True)
    ok = True

    # Inv 22d: on --update, settings.json is written via publish_settings
    # below (merge-aware). On fresh install, it ships via raw copy in the
    # SAME_PATH_FILES loop. Skip the raw copy under --update to avoid
    # clobbering user-added permissions / env vars before the merge runs.
    same_path_to_copy = SAME_PATH_FILES
    if args.update:
        same_path_to_copy = [r for r in SAME_PATH_FILES if r != ".claude/settings.json"]

    for rel in same_path_to_copy:
        ok &= copy_one(src_root, dst_root, rel, rel)

    for src_rel, dst_rel in HOOKS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for src_rel, dst_rel in SKILLS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for src_rel, dst_rel in AGENTS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for src_rel, dst_rel in COMMANDS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for feature, paths in FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            full = f"{base}/{rel}"
            ok &= copy_one(src_root, dst_root, full, full)

    if not ok:
        print("install: aborting due to missing source files", file=sys.stderr)
        return 1

    if args.update:
        # Merge runs AFTER the per-feature refresh has overwritten the
        # feature-local source copy with the fresh upstream bytes, so the
        # merge source is the new content.
        if not _publish_settings_merge(src_root, dst_root):
            print("install: publish_settings merge failed", file=sys.stderr)
            return 1

    rewrite_settings_for_plugin(dst_root)
    write_rabbit_gitignore(dst_root)
    write_version_pin(dst_root)

    total_files = sum(1 for p in dst_root.rglob("*") if p.is_file())
    print(f"Installed {total_files} files to {dst_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
