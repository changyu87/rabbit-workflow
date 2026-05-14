#!/bin/bash
# check-template-schema-producer-consistency.sh — validate that bug-template.json
# top-level keys (excluding _template_version) are a subset of what file-bug.sh
# actually writes.
#
# Known producer set (fields written by file-bug.sh):
#   name, title, status, severity, description, related_feature,
#   filed, filed_by, closed, closed_by, history
#
# Usage: check-template-schema-producer-consistency.sh
# Exit:  0 template keys are consistent; 1 unknown key(s) found.
#
# Version: 1.1.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when template/producer consistency is enforced by a schema registry.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

TEMPLATE="$REPO_ROOT/.claude/features/contract/templates/bug-template.json"

[ ! -f "$TEMPLATE" ] && { echo "ERROR: bug-template.json not found at $TEMPLATE" >&2; exit 2; }

python3 "$SCRIPT_DIR/check-template-schema-producer-consistency.py" "$TEMPLATE"
