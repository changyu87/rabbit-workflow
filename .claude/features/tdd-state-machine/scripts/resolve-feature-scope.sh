#!/usr/bin/env bash
# resolve-feature-scope.sh — build an Opus prompt that maps a request to affected features.
#
# Usage:
#   resolve-feature-scope.sh "<request-description>"
#
# Output: assembled prompt to stdout. Caller passes stdout to Agent(model: opus).
# The Opus agent must respond with JSON: {"features": ["feat-a"], "rationale": "..."}
#
# Version: 1.0.0
# Owner: rabbit-workflow team (tdd-state-machine)
# Deprecation criterion: when feature-scope resolution is automated by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

if [ $# -ne 1 ]; then
  echo "ERROR: usage: resolve-feature-scope.sh <request-description>" >&2
  exit 2
fi

REQUEST="$1"
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
[ -f "$REGISTRY" ] || { echo "ERROR: registry.json not found at $REGISTRY" >&2; exit 1; }

# Build feature context: name, summary, and first Purpose paragraph from spec.md
FEATURE_CONTEXT=""
while IFS= read -r name; do
  [ -z "$name" ] && continue
  path=$(python3 -c "import json; r=json.load(open('$REGISTRY')); print(r.get('features',{}).get('$name',{}).get('path',''))" 2>/dev/null)
  [ -z "$path" ] && continue
  summary=$(python3 -c "import json; r=json.load(open('$REPO_ROOT/$path/feature.json')); print(r.get('summary',''))" 2>/dev/null || echo "")
  spec_purpose=""
  spec_path="$REPO_ROOT/$path/docs/spec/spec.md"
  if [ -f "$spec_path" ]; then
    spec_purpose=$(sed -n '/^## Purpose/,/^##/p' "$spec_path" | head -8 | tail -n +2 | grep -v '^##' | tr '\n' ' ' | sed 's/  */ /g' | sed 's/^ //;s/ $//')
  fi
  FEATURE_CONTEXT="${FEATURE_CONTEXT}
Feature: $name
  Summary: $summary
  Purpose: $spec_purpose
"
done < <(python3 -c "import json; r=json.load(open('$REGISTRY')); [print(k) for k in r.get('features',{}).keys()]" 2>/dev/null)

cat <<PROMPT
You are a feature-scope resolver for a rabbit-workflow repository.

Given a natural-language request, identify which features (from the registry below) the request targets. A request targets a feature if the implementation work will modify files within that feature's directory.

REGISTERED FEATURES:
${FEATURE_CONTEXT}

REQUEST:
${REQUEST}

Respond with ONLY valid JSON on a single line — no markdown, no explanation:
{"features": ["feature-name-1", "feature-name-2"], "rationale": "one sentence"}

Rules:
- Include a feature only if the request requires writing/editing files in that feature's directory.
- If the request touches cross-cutting infrastructure (dispatch scripts, schemas, enforcement), include "contract".
- If the request touches hooks, commands, or skills (other than rabbit-feature-touch), include "rabbit-cage".
- If the request touches rabbit-feature-touch SKILL.md or tdd-step.sh, include "tdd-state-machine".
- Omit features whose files will not be modified.
PROMPT
