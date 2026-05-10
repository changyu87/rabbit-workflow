#!/bin/bash
# rabbit-triage.sh — build a complete triage prompt for a bug filing and print to stdout.
#
# The caller captures this output, invokes an Agent with it, captures the
# TRIAGE: block from the response, and writes vet-triage.json itself.
# This script is deterministic and non-interactive.
#
# Usage:
#   rabbit-triage.sh <feature-dir> <bug-name>
#
# Validates:
#   <feature-dir>/docs/bugs/<bug-name>/bug.json   (required)
#   <feature-dir>/docs/spec/spec.md               (required)
#   <feature-dir>/docs/spec/contract.md           (optional)
#
# Exit:
#   0  prompt printed to stdout
#   1  missing required file
#   2  bad invocation

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRIAGE_TEMPLATE="$SCRIPT_DIR/../templates/triage-template.md"
POLICY_BLOCK_SH="$SCRIPT_DIR/policy-block.sh"

if [ $# -ne 2 ]; then
  echo "ERROR: usage: rabbit-triage.sh <feature-dir> <bug-name>" >&2
  exit 2
fi

FEATURE_DIR="$1"
BUG_NAME="$2"

BUG_FILE="$FEATURE_DIR/docs/bugs/${BUG_NAME}/bug.json"
SPEC_FILE="$FEATURE_DIR/docs/spec/spec.md"
CONTRACT_FILE="$FEATURE_DIR/docs/spec/contract.md"

if [ ! -d "$FEATURE_DIR" ]; then
  echo "ERROR: feature-dir does not exist: $FEATURE_DIR" >&2
  exit 1
fi

if [ ! -f "$BUG_FILE" ]; then
  echo "ERROR: bug file not found: $BUG_FILE" >&2
  exit 1
fi

if [ ! -f "$SPEC_FILE" ]; then
  echo "ERROR: feature spec not found: $SPEC_FILE" >&2
  exit 1
fi

FEATURE_BASENAME="$(basename "$FEATURE_DIR")"
BUG_CONTENT="$(cat "$BUG_FILE")"
SPEC_CONTENT="$(cat "$SPEC_FILE")"

if [ -f "$CONTRACT_FILE" ]; then
  CONTRACT_CONTENT="$(cat "$CONTRACT_FILE")"
else
  CONTRACT_CONTENT="(not present)"
fi

TEMPLATE_CONTENT=""
if [ -f "$TRIAGE_TEMPLATE" ]; then
  TEMPLATE_CONTENT="$(cat "$TRIAGE_TEMPLATE")"
fi

# Emit policy block first (sentinel line + block body).
"$POLICY_BLOCK_SH"

# Assemble and print the triage prompt.
cat <<PROMPT

# TRIAGE REQUEST

You are performing a one-shot read-only bug triage. You do not write files.
Produce exactly one TRIAGE: block in the format specified in the template below.

## Bug: ${BUG_NAME}
${BUG_CONTENT}

## Feature spec: ${FEATURE_BASENAME}
${SPEC_CONTENT}

## Feature contract (if present)
${CONTRACT_CONTENT}

## Output format (follow exactly)
${TEMPLATE_CONTENT}
PROMPT

exit 0
