#!/bin/bash
# render-template.sh — substitute {{key}} placeholders in a template file.
#
# Usage:
#   render-template.sh <template-path> <output-path> [key=value ...]
#
# Reads <template-path>, substitutes each {{key}} placeholder with the
# corresponding value from the key=value args, then writes to <output-path>.
# Unresolved placeholders are left as-is.
#
# Exit:
#   0 success
#   1 template file missing
#   2 invocation error
#
# Version: 1.1.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when template rendering is provided by a native feature mechanism.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -lt 2 ]; then
  echo "ERROR: usage: render-template.sh <template-path> <output-path> [key=value ...]" >&2
  exit 2
fi

TEMPLATE="$1"
OUTPUT="$2"
shift 2

if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: template file not found: $TEMPLATE" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required" >&2
  exit 1
fi

python3 "$SCRIPT_DIR/render-template.py" "$TEMPLATE" "$OUTPUT" "$@"
