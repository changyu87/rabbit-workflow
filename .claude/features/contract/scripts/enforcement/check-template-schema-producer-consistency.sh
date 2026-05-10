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

set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"

TEMPLATE="$REPO_ROOT/.claude/features/contract/templates/bug-template.json"

[ ! -f "$TEMPLATE" ] && { echo "ERROR: bug-template.json not found at $TEMPLATE" >&2; exit 2; }

# Known producer fields (what file-bug.sh writes)
PRODUCER_FIELDS="name title status severity description related_feature filed filed_by closed closed_by history"

fail=0

# Extract top-level keys from bug-template.json using python3
keys="$(python3 -c "
import json, sys
with open('$TEMPLATE') as f:
    data = json.load(f)
for k in data.keys():
    if k != '_template_version':
        print(k)
" 2>&1)"

if [ $? -ne 0 ]; then
  echo "ERROR: failed to parse $TEMPLATE: $keys" >&2
  exit 2
fi

while IFS= read -r key; do
  [ -z "$key" ] && continue
  found=0
  for pf in $PRODUCER_FIELDS; do
    [ "$key" = "$pf" ] && found=1 && break
  done
  if [ "$found" -eq 0 ]; then
    echo "UNKNOWN KEY: '$key' in bug-template.json is not in the file-bug.sh producer set" >&2
    fail=1
  fi
done <<< "$keys"

if [ "$fail" -ne 0 ]; then
  echo "FAIL: template-schema-producer consistency check failed" >&2
  exit 1
fi

echo "OK: all bug-template.json keys are consistent with file-bug.sh producer set"
exit 0
