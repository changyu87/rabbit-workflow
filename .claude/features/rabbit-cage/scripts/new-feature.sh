#!/bin/bash
# new-feature.sh — scaffold a feature directory at any path with the rabbit
# feature-skeleton schema. User-mode: works wherever you point it; the user's
# own project at /any/path/projA/features/, the rabbit dev workspace at
# .claude/features/, anywhere.
#
# Usage:
#   new-feature.sh <root> <name> [--owner <name>] [--description <desc>]
#
# Exit:
#   0 success
#   1 invalid name or target exists
#   2 invocation error

set -u

usage() {
  cat >&2 <<EOF
usage: new-feature.sh <root> <name> [--owner <name>] [--description <desc>]
  <root>  parent directory under which <name>/ will be created
  <name>  lowercase kebab-case, [a-z][a-z0-9-]*, max 50 chars
EOF
}

ROOT="${1:-}"; NAME="${2:-}"
[ -z "$ROOT" ] || [ -z "$NAME" ] && { usage; exit 2; }
shift 2

OWNER=""; DESC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --owner)       OWNER="$2"; shift 2 ;;
    --description) DESC="$2";  shift 2 ;;
    -h|--help)     usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

# Validate name
if ! echo "$NAME" | grep -qE '^[a-z][a-z0-9-]{0,49}$'; then
  echo "ERROR: invalid name '$NAME' (must be lowercase kebab-case starting with a letter, max 50 chars)" >&2
  exit 1
fi

# Auto-create parent root (mkdir -p) — friendlier for user-mode bootstrapping
mkdir -p "$ROOT" 2>/dev/null || { echo "ERROR: cannot create root '$ROOT'" >&2; exit 1; }

TARGET="$ROOT/$NAME"
if [ -e "$TARGET" ]; then
  echo "ERROR: '$TARGET' already exists" >&2
  exit 1
fi

OWNER="${OWNER:-${USER:-unknown}}"
DESC="${DESC:-TODO: one-sentence purpose}"
TODAY="$(date +%Y-%m-%d)"

mkdir -p "$TARGET/test" "$TARGET/scripts" "$TARGET/docs/spec" "$TARGET/docs/bugs"

# feature.json — structured manifest, source of truth
cat > "$TARGET/feature.json" <<JSON
{
  "name": "$NAME",
  "version": "0.1.0",
  "owner": "$OWNER",
  "tdd_state": "spec",
  "summary": "$NAME feature",
  "surface": {
    "hooks": [],
    "commands": [],
    "skills": []
  },
  "deprecation_criterion": "TBD — set after first review"
}
JSON

# docs/spec/spec.md — LLM-prose view
cat > "$TARGET/docs/spec/spec.md" <<MD
# $NAME

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [\`feature.json\`](../../feature.json).

## Purpose

$DESC

## Schema / Behavior

TODO: describe what this feature does in narrative form.

## What this feature does NOT define

TODO: name adjacent concerns and which features own them. (Bounded scope.)

## Tests

\`test/run.sh\` runs the end-to-end suite. Currently red (expected: this
feature is in \`tdd_state: spec\`; tests have not been authored yet).

Per the TDD state machine: author tests next, transition to \`test-red\`,
then implement, transition to \`impl\`, etc.
MD

# docs/spec/contract.md — LLM-prose contract
cat > "$TARGET/docs/spec/contract.md" <<MD
# Contract — $NAME

## Reads

- TODO: list paths or patterns this feature reads.

## Writes

- TODO: list paths this feature writes (or "None" if read-only).

## Invokes

- TODO: list external tools, scripts, or other features this feature invokes.

## Inputs / Outputs

TODO: per-script I/O documentation.

## Cross-scope handoff

TODO: name what this feature delegates to other features.

## Versioning

- Current version: \`0.1.0\`.
- Bump rules: TODO.
MD

# docs/bugs/.gitkeep — ensure bugs directory is tracked
touch "$TARGET/docs/bugs/.gitkeep"

# test/run.sh — placeholder, exits non-zero (TDD red)
cat > "$TARGET/test/run.sh" <<'SH'
#!/bin/bash
# Placeholder. Author real tests here, then transition tdd_state to test-red.
# This file exits non-zero so the feature is honestly in TDD red until tests
# are authored.
echo "no tests yet — author tests in this file (or sibling test-*.sh) and transition tdd_state to test-red" >&2
exit 1
SH
chmod +x "$TARGET/test/run.sh"

echo "scaffolded: $TARGET"

# Optional self-validation if contract's validator is reachable
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
# Try common locations: repo-anchored path first, then well-known fallback.
VAL=""
for candidate in \
    "$REPO_ROOT/.claude/features/contract/scripts/validate-feature.sh" \
    ".claude/features/contract/scripts/validate-feature.sh"; do
  if [ -x "$candidate" ]; then VAL="$candidate"; break; fi
done

if [ -n "$VAL" ]; then
  if "$VAL" "$TARGET" >/dev/null 2>&1; then
    echo "validated: passes feature schema"
  else
    echo "WARNING: scaffolded feature does not yet pass validate-feature.sh (expected — fill in TODOs)" >&2
  fi
fi

exit 0
