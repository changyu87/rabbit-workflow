#!/bin/bash
# rabbit-triage.sh — build a triage prompt for a bug filing.
#
# Usage:
#   rabbit-triage.sh <feature-dir> <bug-name>
#
# Loads the bug JSON from <feature-dir>/docs/bugs/<bug-name>.json and the
# feature spec from <feature-dir>/docs/spec/spec.md, builds a one-shot triage
# prompt using triage-template.md, and prints what it would invoke.
#
# STUB: Full implementation in Step 6. Currently prints the assembled prompt.
#
# Exit:
#   0 success
#   1 bug or spec file missing
#   2 invocation error

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRIAGE_TEMPLATE="$SCRIPT_DIR/../templates/triage-template.md"

if [ $# -ne 2 ]; then
  echo "ERROR: usage: rabbit-triage.sh <feature-dir> <bug-name>" >&2
  exit 2
fi

FEATURE_DIR="$1"
BUG_NAME="$2"

BUG_FILE="$FEATURE_DIR/docs/bugs/${BUG_NAME}.json"
SPEC_FILE="$FEATURE_DIR/docs/spec/spec.md"

if [ ! -f "$BUG_FILE" ]; then
  echo "ERROR: bug file not found: $BUG_FILE" >&2
  exit 1
fi

if [ ! -f "$SPEC_FILE" ]; then
  echo "ERROR: feature spec not found: $SPEC_FILE" >&2
  exit 1
fi

BUG_CONTENT="$(cat "$BUG_FILE")"
SPEC_CONTENT="$(cat "$SPEC_FILE")"
TEMPLATE_CONTENT=""
if [ -f "$TRIAGE_TEMPLATE" ]; then
  TEMPLATE_CONTENT="$(cat "$TRIAGE_TEMPLATE")"
fi

cat <<PROMPT
[stub] rabbit-triage — would invoke one-shot triage Agent with:

=== BUG ===
$BUG_CONTENT

=== FEATURE SPEC ===
$SPEC_CONTENT

=== TRIAGE TEMPLATE ===
$TEMPLATE_CONTENT

[stub] Full Agent invocation not implemented (Step 6).
PROMPT

exit 0
