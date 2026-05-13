#!/usr/bin/env bash
# build.sh — unified workspace artifact builder.
#
# Reads .claude/features/contract/build-contract.json and builds all declared targets.
# Usage: build.sh [REPO_ROOT]
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively manages workspace artifact generation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
CONTRACT="$REPO_ROOT/.claude/features/contract/build-contract.json"
GENERATE_CLAUDE_MD="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

[ -f "$CONTRACT" ] || { echo "build: contract not found: $CONTRACT" >&2; exit 1; }

python3 - "$REPO_ROOT" "$CONTRACT" "$GENERATE_CLAUDE_MD" <<'PYEOF'
import json, os, shutil, subprocess, sys

repo_root, contract_path, generate_script = sys.argv[1], sys.argv[2], sys.argv[3]

with open(contract_path) as f:
    contract = json.load(f)

errors = 0
for target in contract.get("targets", []):
    name = target["name"]
    ttype = target["type"]
    destination = os.path.join(repo_root, target["destination"])

    if ttype == "generate-claude-md":
        env = dict(os.environ)
        env["RABBIT_ROOT"] = repo_root
        result = subprocess.run(
            ["bash", generate_script, "--write", repo_root],
            capture_output=True, text=True,
            env=env
        )
        if result.returncode != 0:
            print(f"  [error] {name}: generate-claude-md failed\n{result.stderr}", file=sys.stderr)
            errors += 1
        else:
            print(f"  [built] {name}")

    elif ttype == "copy-file":
        source = os.path.join(repo_root, target["source"])
        if not os.path.isfile(source):
            print(f"  [error] build: source not found: {target['source']}", file=sys.stderr)
            errors += 1
            continue
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        print(f"  [built] {name}")

    else:
        print(f"  [error] unknown type '{ttype}' for target '{name}'", file=sys.stderr)
        errors += 1

if errors:
    print(f"\nbuild: {errors} error(s)", file=sys.stderr)
    sys.exit(1)
PYEOF
