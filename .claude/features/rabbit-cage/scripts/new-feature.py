#!/usr/bin/env python3
"""new-feature.py — scaffold a feature directory at any path with the rabbit
feature-skeleton schema.

Usage:
  new-feature.py <root> <name> [--owner <name>] [--description <desc>]

Exit:
  0 success
  1 invalid name or target exists
  2 invocation error
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path


def usage(stream=sys.stderr) -> None:
    stream.write(
        "usage: new-feature.py <root> <name> [--owner <name>] [--description <desc>]\n"
        "  <root>  parent directory under which <name>/ will be created\n"
        "  <name>  lowercase kebab-case, [a-z][a-z0-9-]*, max 50 chars\n"
    )


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] in ("-h", "--help"):
        usage(sys.stderr if len(args) < 2 else sys.stdout)
        return 2 if len(args) < 2 else 0

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

    for sub in ("test", "scripts", "docs/spec", "docs/bugs"):
        (target / sub).mkdir(parents=True)

    feature_json = (
        '{\n'
        f'  "name": "{name}",\n'
        '  "version": "0.1.0",\n'
        f'  "owner": "{owner}",\n'
        '  "tdd_state": "spec",\n'
        f'  "summary": "{name} feature",\n'
        '  "surface": {\n'
        '    "hooks": [],\n'
        '    "commands": [],\n'
        '    "skills": []\n'
        '  },\n'
        '  "deprecation_criterion": "TBD — set after first review"\n'
        '}\n'
    )
    (target / "feature.json").write_text(feature_json)

    spec_md = (
        f"# {name}\n\n"
        "> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).\n"
        "> Structured source of truth is [`feature.json`](../../feature.json).\n\n"
        "## Purpose\n\n"
        f"{desc}\n\n"
        "## Schema / Behavior\n\n"
        "TODO: describe what this feature does in narrative form.\n\n"
        "## What this feature does NOT define\n\n"
        "TODO: name adjacent concerns and which features own them. (Bounded scope.)\n\n"
        "## Tests\n\n"
        "`test/run.sh` runs the end-to-end suite. Currently red (expected: this\n"
        "feature is in `tdd_state: spec`; tests have not been authored yet).\n\n"
        "Per the TDD state machine: author tests next, transition to `test-red`,\n"
        "then implement, transition to `impl`, etc.\n"
    )
    (target / "docs/spec/spec.md").write_text(spec_md)

    contract_md = (
        f"# Contract — {name}\n\n"
        "## Reads\n\n"
        "- TODO: list paths or patterns this feature reads.\n\n"
        "## Writes\n\n"
        '- TODO: list paths this feature writes (or "None" if read-only).\n\n'
        "## Invokes\n\n"
        "- TODO: list external tools, scripts, or other features this feature invokes.\n\n"
        "## Inputs / Outputs\n\n"
        "TODO: per-script I/O documentation.\n\n"
        "## Cross-scope handoff\n\n"
        "TODO: name what this feature delegates to other features.\n\n"
        "## Versioning\n\n"
        "- Current version: `0.1.0`.\n"
        "- Bump rules: TODO.\n"
    )
    (target / "docs/spec/contract.md").write_text(contract_md)

    (target / "docs/bugs/.gitkeep").touch()

    run_sh = (
        "#!/bin/bash\n"
        "# Placeholder. Author real tests here, then transition tdd_state to test-red.\n"
        "# This file exits non-zero so the feature is honestly in TDD red until tests\n"
        "# are authored.\n"
        'echo "no tests yet — author tests in this file (or sibling test-*.sh) and transition tdd_state to test-red" >&2\n'
        "exit 1\n"
    )
    run_path = target / "test/run.sh"
    run_path.write_text(run_sh)
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
        candidates.append(Path(repo_root) / ".claude/features/contract/scripts/validate-feature.sh")
    candidates.append(Path(".claude/features/contract/scripts/validate-feature.sh"))
    validator = None
    for c in candidates:
        if c.is_file() and os.access(str(c), os.X_OK):
            validator = c
            break
    if validator is not None:
        rc = subprocess.call(
            [str(validator), str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if rc == 0:
            print("validated: passes feature schema")
        else:
            sys.stderr.write(
                "WARNING: scaffolded feature does not yet pass validate-feature.sh "
                "(expected — fill in TODOs)\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
