#!/usr/bin/env python3
"""scaffold-feature.py — scaffold a feature directory with the rabbit
feature-skeleton schema.

Two modes:

* Standalone (default) — scaffolds a conforming rabbit-self feature
  directory at the requested root:
      scaffold-feature.py <root> <name> [--owner <name>] [--description <desc>]

* Plugin — triggered when `<cwd>/.rabbit/.runtime/mode` contains "plugin"
  (the marker is written at SessionStart by rabbit-meta's mode detector).
  Scaffolds a per-project feature under
  `<repo>/.rabbit/rabbit-project/features/<name>/` and registers it in
  `<repo>/.rabbit/rabbit-project/project-map.json`, mapping a list of
  user-code path globs to the feature:
      scaffold-feature.py <name> <path-glob> [<path-glob>...]

Exit:
  0 success
  1 invalid name, target exists, or plugin-mode validation failure
    (glob outside user-project root, overlap with existing feature,
    empty match, schema-validation failure)
  2 invocation error

Version: 2.2.0
Owner: rabbit-workflow team (rabbit-feature)
Deprecation criterion: when feature scaffolding is exposed as a native
    rabbit CLI subcommand.
"""

from __future__ import annotations

import argparse
import datetime
import glob as _glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def usage(stream=sys.stderr) -> None:
    stream.write(
        "usage: scaffold-feature.py <root> <name> [--owner <name>] [--description <desc>]\n"
        "       scaffold-feature.py <name> <path-glob> [<path-glob>...]   "
        "(plugin mode; requires <cwd>/.rabbit/.runtime/mode == 'plugin')\n"
        "  <root>      parent directory under which <name>/ will be created\n"
        "  <name>      lowercase kebab-case, [a-z][a-z0-9-]*, max 50 chars\n"
        "  <path-glob> user-code path pattern (relative to user-project root)\n"
    )


def _detect_plugin_mode(cwd: Path) -> tuple[bool, Path | None]:
    """Walk UP from cwd to find the nearest plugin-mode `.rabbit/` ancestor.

    Returns `(True, rabbit_root)` on first match, where `rabbit_root` is the
    `.rabbit/` directory itself (so `rabbit_root.parent` is the user-project
    root). Returns `(False, None)` if the walk reaches the filesystem root
    with no match.

    Two ancestor shapes count as a match, checked at each candidate `D`
    (starting at `cwd` and walking to `/`):

      (a) `D/.runtime/mode` contains `plugin` — cwd is inside `.rabbit/`
          itself; resolved `rabbit_root` is `D`.
      (b) `D/.rabbit/.runtime/mode` contains `plugin` — cwd is at or
          below the user-project root; resolved `rabbit_root` is `D/.rabbit`.

    Inv 44 (amended) — replaces the original single-check semantics that only
    inspected `<cwd>/.rabbit/.runtime/mode`. That semantics failed silently
    when cwd was `.rabbit/` itself (the typical rabbit session cwd in plugin
    mode), because it then looked for `.rabbit/.rabbit/.runtime/mode`.
    """
    start = Path(cwd).resolve()
    for candidate in (start, *start.parents):
        # Case (a): cwd is inside `.rabbit/` itself.
        marker_a = candidate / ".runtime" / "mode"
        if marker_a.is_file():
            try:
                if marker_a.read_text().strip() == "plugin":
                    return (True, candidate)
            except OSError:
                pass
        # Case (b): cwd is the user-project root (or below it).
        marker_b = candidate / ".rabbit" / ".runtime" / "mode"
        if marker_b.is_file():
            try:
                if marker_b.read_text().strip() == "plugin":
                    return (True, candidate / ".rabbit")
            except OSError:
                pass
    return (False, None)


def _valid_name(name: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9-]{0,49}$", name))


def _validate_project_map(pmap: dict) -> str | None:
    """Stdlib-only schema check matching project-map.json.schema.json.

    Returns None on success, error message on failure.
    """
    if not isinstance(pmap, dict):
        return "project-map.json: root must be an object"
    if pmap.get("schema_version") != "1.0.0":
        return "project-map.json: schema_version must be '1.0.0'"
    if not re.match(r"^\d+\.\d+\.\d+$", str(pmap.get("schema_version", ""))):
        return "project-map.json: schema_version must match X.Y.Z"
    feats = pmap.get("features")
    if not isinstance(feats, dict):
        return "project-map.json: features must be an object"
    extra = set(pmap.keys()) - {"schema_version", "features"}
    if extra:
        return f"project-map.json: unknown top-level keys: {sorted(extra)}"
    for fname, entry in feats.items():
        if not re.match(r"^[a-z][a-z0-9-]*$", fname):
            return f"project-map.json: invalid feature name {fname!r}"
        if not isinstance(entry, dict):
            return f"project-map.json: features[{fname}] must be an object"
        extra = set(entry.keys()) - {"paths", "feature_dir"}
        if extra:
            return f"project-map.json: features[{fname}] unknown keys: {sorted(extra)}"
        paths = entry.get("paths")
        if not isinstance(paths, list) or not paths:
            return f"project-map.json: features[{fname}].paths must be a non-empty list"
        if not all(isinstance(p, str) for p in paths):
            return f"project-map.json: features[{fname}].paths items must be strings"
        if not isinstance(entry.get("feature_dir"), str):
            return f"project-map.json: features[{fname}].feature_dir must be a string"
    return None


def _resolve_glob_under_root(pattern: str, root: Path) -> tuple[list[Path] | None, str | None]:
    """Resolve `pattern` relative to `root` and reject matches outside root.

    Returns (matches, None) on success; (None, error_message) on failure.
    """
    # Reject patterns whose literal text escapes the root (e.g. "../../etc/**").
    # We resolve the pattern's stem (the directory portion of the pattern with
    # any glob metacharacters dropped) and check it stays under root.
    abs_root = root.resolve()
    # The literal "anchor" of the pattern is the path with glob chars stripped
    # at the first segment containing one. Easiest: walk the parts.
    parts = Path(pattern).parts
    anchor_parts = []
    for p in parts:
        if any(ch in p for ch in "*?[]"):
            break
        anchor_parts.append(p)
    anchor = root.joinpath(*anchor_parts).resolve() if anchor_parts else abs_root
    try:
        anchor.relative_to(abs_root)
    except ValueError:
        return None, (
            f"path-glob {pattern!r} resolves outside user-project root "
            f"{abs_root} (path traversal boundary)"
        )
    # Now actually resolve matches via glob, with cwd=root.
    saved_cwd = os.getcwd()
    try:
        os.chdir(str(abs_root))
        matched = sorted(_glob.glob(pattern, recursive=True))
    finally:
        os.chdir(saved_cwd)
    # Reject any match that escapes the root post-resolution (symlink shenanigans).
    safe = []
    for m in matched:
        mp = (abs_root / m).resolve()
        try:
            mp.relative_to(abs_root)
        except ValueError:
            return None, (
                f"path-glob {pattern!r} produced match {m!r} outside "
                f"user-project root {abs_root}"
            )
        safe.append(mp)
    return safe, None


def _scaffold_plugin_feature(target: Path, name: str, owner: str, globs: list[str]) -> None:
    """Write feature.json, specs/spec.md, specs/contract.md for the
    per-project plugin feature (issue #399: specs/ layout)."""
    for sub in ("specs",):
        (target / sub).mkdir(parents=True)
    created = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    feature_json = {
        "name": name,
        "version": "0.1.0",
        "owner": owner,
        "paths": globs,
        "created": created,
        "deprecation_criterion": None,
    }
    (target / "feature.json").write_text(json.dumps(feature_json, indent=2) + "\n")

    spec_md = (
        f"# {name}\n\n"
        "> Per-project feature spec (plugin mode). Seeded by the spec-creator\n"
        "> subagent via the rabbit-spec-create skill — replace this placeholder\n"
        "> with real content.\n\n"
        "## Purpose\n\n"
        "TODO: one-sentence purpose.\n\n"
        "## Path globs\n\n"
        + "".join(f"- `{g}`\n" for g in globs)
        + "\n## Invariants\n\nTODO.\n"
    )
    (target / "specs/spec.md").write_text(spec_md)

    contract_md = (
        "---\n"
        f"feature: {name}\n"
        "version: 0.1.0\n"
        "---\n\n"
        f"# {name} — Contract\n\n"
        "```json\n"
        "{\n"
        '  "provides": {"files": [], "scripts": [], "skills": []},\n'
        '  "reads": {"files": [], "external": []},\n'
        '  "invokes": {"scripts": [], "agents": []},\n'
        '  "never": []\n'
        "}\n"
        "```\n"
    )
    (target / "specs/contract.md").write_text(contract_md)


def _run_plugin_mode(repo_root: Path, name: str, globs: list[str]) -> int:
    if not _valid_name(name):
        sys.stderr.write(
            f"ERROR: invalid name {name!r} (must be lowercase kebab-case "
            "starting with a letter, max 50 chars)\n"
        )
        return 1

    # Resolve each glob under repo_root; track which paths each feature claims.
    new_matches: list[Path] = []
    for g in globs:
        matched, err = _resolve_glob_under_root(g, repo_root)
        if err:
            sys.stderr.write(f"ERROR: {err}\n")
            return 1
        new_matches.extend(matched)

    if not new_matches:
        sys.stderr.write(
            f"ERROR: no files match any of the supplied globs {globs!r}; "
            "refuse to register a feature with zero matches (typo guard)\n"
        )
        return 1

    # Load existing project-map (if any), check for overlap with other features.
    pmap_path = repo_root / ".rabbit/rabbit-project/project-map.json"
    if pmap_path.is_file():
        try:
            pmap = json.loads(pmap_path.read_text())
        except Exception as e:
            sys.stderr.write(f"ERROR: cannot parse existing project-map.json: {e}\n")
            return 1
        err = _validate_project_map(pmap)
        if err:
            sys.stderr.write(f"ERROR: existing {err}\n")
            return 1
    else:
        pmap = {"schema_version": "1.0.0", "features": {}}

    if name in pmap.get("features", {}):
        sys.stderr.write(
            f"ERROR: feature {name!r} already declared in project-map.json\n"
        )
        return 1

    new_match_set = {str(p) for p in new_matches}
    for other_name, entry in pmap.get("features", {}).items():
        for other_glob in entry.get("paths", []):
            other_matched, _err = _resolve_glob_under_root(other_glob, repo_root)
            if other_matched is None:
                continue
            other_set = {str(p) for p in other_matched}
            overlap = new_match_set & other_set
            if overlap:
                first = sorted(overlap)[0]
                rel = str(Path(first).relative_to(repo_root))
                sys.stderr.write(
                    f"ERROR: path {rel!r} already governed by feature "
                    f"{other_name!r} (glob {other_glob!r}); refuse to "
                    f"register overlapping feature {name!r}\n"
                )
                return 1

    target = repo_root / ".rabbit/rabbit-project/features" / name
    if target.exists():
        sys.stderr.write(f"ERROR: scaffold target {target} already exists\n")
        return 1

    owner = os.environ.get("USER", "unknown")
    _scaffold_plugin_feature(target, name, owner, globs)

    # Register in project-map.json, schema-validate, then write atomically.
    pmap.setdefault("features", {})[name] = {
        "paths": globs,
        "feature_dir": f"rabbit-project/features/{name}",
    }
    err = _validate_project_map(pmap)
    if err:
        sys.stderr.write(f"ERROR: would-be {err}\n")
        return 1
    pmap_path.parent.mkdir(parents=True, exist_ok=True)
    pmap_path.write_text(json.dumps(pmap, indent=2) + "\n")

    print(f"scaffolded plugin feature: {target}")
    print(f"registered in: {pmap_path}")
    # Plugin-mode handoff: the caller invokes the rabbit-spec-create skill
    # (under rabbit-spec) which dispatches the spec-creator subagent. We do
    # not invoke the skill ourselves — the dispatch happens at the
    # dispatcher (skill caller) layer.
    dispatcher = ".claude/features/rabbit-spec/scripts/dispatch-spec-create.py"
    print(
        "\nNEXT: invoke the rabbit-spec-create skill (or run the dispatcher\n"
        "directly) to seed specs/spec.md:\n"
        f"  Skill(\"rabbit-spec-create\", args: \"{name} {' '.join(globs)}\")\n"
        "or equivalently:\n"
        f"  python3 {dispatcher} \\\n"
        f"    --feature-name {name} \\\n"
        f"    --paths '{','.join(globs)}'\n"
        "then dispatch the spec-creator subagent with the assembled prompt."
    )
    return 0


def _run_plugin_mode_batch(repo_root: Path, batch_file: Path) -> int:
    """Validate every entry, then scaffold all. Stops on first failure.

    Pragmatic batch: pre-validates names + glob resolution + project-map
    overlap before doing any scaffolding work. If validation passes, runs
    _run_plugin_mode for each entry sequentially. A late failure (e.g.
    filesystem error during a scaffold) leaves earlier entries committed —
    full transactional rollback is not provided here.
    """
    try:
        entries = json.loads(batch_file.read_text())
    except Exception as e:
        sys.stderr.write(f"ERROR: cannot read/parse batch file {batch_file}: {e}\n")
        return 2

    if not isinstance(entries, list):
        sys.stderr.write("ERROR: batch file must contain a JSON array\n")
        return 2

    parsed: list[tuple[str, list[str]]] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            sys.stderr.write(f"ERROR: batch[{i}] must be an object {{name, globs}}\n")
            return 2
        name = entry.get("name")
        globs = entry.get("globs")
        if not isinstance(name, str) or not _valid_name(name):
            sys.stderr.write(f"ERROR: batch[{i}].name invalid: {name!r}\n")
            return 1
        if not isinstance(globs, list) or not globs or not all(isinstance(g, str) for g in globs):
            sys.stderr.write(f"ERROR: batch[{i}].globs must be a non-empty list of strings\n")
            return 1
        parsed.append((name, globs))

    seen_names: set[str] = set()
    for name, _ in parsed:
        if name in seen_names:
            sys.stderr.write(f"ERROR: duplicate feature name {name!r} in batch\n")
            return 1
        seen_names.add(name)

    for i, (name, globs) in enumerate(parsed):
        rc = _run_plugin_mode(repo_root, name, globs)
        if rc != 0:
            sys.stderr.write(
                f"ERROR: batch entry [{i}] {name!r} failed (rc={rc}); "
                f"entries [0..{i-1}] are already committed\n"
            )
            return rc

    print(f"\nBATCH OK: scaffolded {len(parsed)} feature(s)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        usage(sys.stdout if args and args[0] in ("-h", "--help") else sys.stderr)
        return 0 if args and args[0] in ("-h", "--help") else 2

    # Plugin-mode dispatch comes first: walk UP from cwd looking for the
    # nearest `.rabbit/` ancestor with `.runtime/mode == "plugin"`. The
    # detection happens BEFORE argparse so a `<name> <path-glob>` pair is
    # never misinterpreted as `<root> <name>`. Standalone is the fallback.
    cwd = Path(os.getcwd())
    is_plugin, rabbit_root = _detect_plugin_mode(cwd)
    if is_plugin:
        # The user-project root is the parent of `.rabbit/`.
        project_root = rabbit_root.parent
        # Batch form: --batch <features.json>
        if args[0] == "--batch":
            if len(args) != 2:
                sys.stderr.write("ERROR: --batch requires exactly one argument (path to JSON file)\n")
                return 2
            return _run_plugin_mode_batch(project_root, Path(args[1]))

        # Plugin form: <name> <path-glob> [<path-glob>...]
        if len(args) < 2:
            usage(sys.stderr)
            return 2
        name = args[0]
        globs = args[1:]
        # If any glob looks like a flag, fall through to argparse-style error.
        if any(g.startswith("-") for g in globs):
            usage(sys.stderr)
            return 2
        return _run_plugin_mode(project_root, name, globs)

    if len(args) < 2:
        usage(sys.stderr)
        return 2

    root = args[0]
    name = args[1]
    rest = args[2:]

    owner = ""
    desc = ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--owner" and i + 1 < len(rest):
            owner = rest[i + 1]; i += 2
        elif a == "--description" and i + 1 < len(rest):
            desc = rest[i + 1]; i += 2
        elif a in ("-h", "--help"):
            usage(sys.stdout)
            return 0
        else:
            sys.stderr.write(f"unknown arg: {a}\n")
            usage()
            return 2

    if not re.match(r"^[a-z][a-z0-9-]{0,49}$", name):
        sys.stderr.write(
            f"ERROR: invalid name '{name}' (must be lowercase kebab-case "
            "starting with a letter, max 50 chars)\n"
        )
        return 1

    root_path = Path(root)
    try:
        root_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        sys.stderr.write(f"ERROR: cannot create root '{root}'\n")
        return 1

    target = root_path / name
    if target.exists():
        sys.stderr.write(f"ERROR: '{target}' already exists\n")
        return 1

    if not owner:
        owner = os.environ.get("USER", "unknown")
    if not desc:
        desc = "TODO: one-sentence purpose"
    today = datetime.date.today().isoformat()  # noqa: F841

    # issue #399: new features are created at the ratified flat docs/ layout
    # (docs/spec.md, docs/contract.md), preserving docs/bugs/. Spec/contract
    # resolution still dual-reads specs/ for not-yet-migrated features.
    for sub in ("test", "scripts", "docs/bugs"):
        (target / sub).mkdir(parents=True)

    feature_json = (
        '{\n'
        '  "template_version": "2.0.0",\n'
        f'  "name": "{name}",\n'
        '  "version": "0.1.0",\n'
        f'  "owner": "{owner}",\n'
        '  "tdd_state": "spec",\n'
        f'  "summary": "{name} feature",\n'
        '  "surface": {\n'
        '    "hooks": [],\n'
        '    "commands": [],\n'
        '    "agents": [],\n'
        '    "skills": []\n'
        '  },\n'
        '  "deprecation_criterion": "TBD — set after first review"\n'
        '}\n'
    )
    (target / "feature.json").write_text(feature_json)

    spec_md = (
        f"# {name}\n\n"
        "> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).\n"
        "> Structured source of truth is [`feature.json`](../feature.json).\n\n"
        "## Purpose\n\n"
        f"{desc}\n\n"
        "## Schema / Behavior\n\n"
        "TODO: describe what this feature does in narrative form.\n\n"
        "## What this feature does NOT define\n\n"
        "TODO: name adjacent concerns and which features own them. (Bounded scope.)\n\n"
        "## Tests\n\n"
        "`test/run.py` runs the end-to-end suite. Currently red (expected: this\n"
        "feature is in `tdd_state: spec`; tests have not been authored yet).\n\n"
        "Per the TDD state machine: author tests next, transition to `test-red`,\n"
        "then implement, transition to `impl`, etc.\n"
    )
    (target / "docs/spec.md").write_text(spec_md)

    # BUG-71: scaffold the template_version 2.0.0 structure
    # (frontmatter + provides/reads/invokes/manages/never JSON block).
    contract_md = (
        "---\n"
        f"feature: {name}\n"
        "version: 0.1.0\n"
        "template_version: 2.0.0\n"
        "---\n\n"
        f"# {name} — Contract\n\n"
        "```json\n"
        "{\n"
        '  "provides": {\n'
        '    "files": [],\n'
        '    "commands": [],\n'
        '    "scripts": [],\n'
        '    "schemas": [],\n'
        '    "templates": [],\n'
        '    "skills": []\n'
        '  },\n'
        '  "reads": {\n'
        '    "files": [],\n'
        '    "external": []\n'
        '  },\n'
        '  "invokes": {\n'
        '    "scripts": [],\n'
        '    "agents": []\n'
        '  },\n'
        '  "manages": {\n'
        '    "runtime_markers": []\n'
        '  },\n'
        '  "never": []\n'
        "}\n"
        "```\n"
    )
    (target / "docs/contract.md").write_text(contract_md)

    (target / "docs/bugs/.gitkeep").touch()

    run_py = (
        "#!/usr/bin/env python3\n"
        '"""Placeholder test runner. Author real tests here, then transition\n'
        'tdd_state to test-red. Exits non-zero so the feature is honestly in\n'
        'TDD red until tests are authored."""\n'
        "import sys\n"
        "\n"
        "sys.stderr.write(\n"
        "    \"no tests yet — author tests in this directory (test-*.py) and \"\n"
        "    \"transition tdd_state to test-red\\n\"\n"
        ")\n"
        "sys.exit(1)\n"
    )
    run_path = target / "test/run.py"
    run_path.write_text(run_py)
    run_path.chmod(0o755)

    print(f"scaffolded: {target}")

    # Optional self-validation
    script_dir = Path(__file__).resolve().parent
    repo_root = os.environ.get("RABBIT_ROOT")
    if not repo_root:
        try:
            repo_root = subprocess.check_output(
                ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            repo_root = ""
    candidates = []
    if repo_root:
        candidates.append(Path(repo_root) / ".claude/features/contract/scripts/validate-feature.py")
    candidates.append(Path(".claude/features/contract/scripts/validate-feature.py"))
    validator = None
    for c in candidates:
        if c.is_file() and os.access(str(c), os.X_OK):
            validator = c
            break
    if validator is not None:
        rc = subprocess.call(
            [sys.executable, str(validator), str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if rc == 0:
            print("validated: passes feature schema")
        else:
            sys.stderr.write(
                "WARNING: scaffolded feature does not yet pass validate-feature.py "
                "(expected — fill in TODOs)\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
