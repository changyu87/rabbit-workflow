#!/bin/bash
# resolve-scope.sh — build a prompt that maps a request to affected rabbit features.
#
# Usage:
#   resolve-scope.sh "<request-description>"
#
# Output: assembled prompt to stdout. Caller dispatches with default model.
# Agent response JSON: {"features": ["feat-a"], "rationale": "one sentence"}
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-feature-scope)
# Deprecation criterion: when feature-scope resolution is automated by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"

if [ $# -ne 1 ]; then
  echo "ERROR: usage: resolve-scope.sh <request-description>" >&2
  exit 2
fi

REQUEST="$1"

[ -x "$FIND_FEATURE" ] || { echo "ERROR: find-feature.sh not found: $FIND_FEATURE" >&2; exit 1; }

FEATURE_CONTEXT=$(bash "$FIND_FEATURE" --list-json 2>/dev/null | python3 "$SCRIPT_DIR/format-feature-context.py" 2>/dev/null)

cat <<PROMPT
You are a feature-scope resolver for a rabbit-workflow repository.

Given a natural-language request, identify which features the request targets.
A request targets a feature if the implementation work will modify files within
that feature's directory.

REGISTERED FEATURES:
${FEATURE_CONTEXT}

REQUEST:
${REQUEST}

Respond with ONLY valid JSON on a single line — no markdown, no explanation:
{"features": ["feature-name-1", "feature-name-2"], "rationale": "one sentence"}

Rules:
- Include a feature only if the request requires writing/editing files in that feature's directory.
- If the request touches cross-cutting infrastructure (dispatch scripts, schemas, enforcement), include "contract".
- If the request touches hooks, commands, or skills surface, include "rabbit-cage".
- Omit features whose files will not be modified.
- Return an empty features list [] if no features are targeted.
PROMPT
