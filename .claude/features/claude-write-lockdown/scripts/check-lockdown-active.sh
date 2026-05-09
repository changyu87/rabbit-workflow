#!/bin/bash
# check-lockdown-active.sh — verify a settings.json carries the .claude/**
# Write/Edit deny rules.
#
# Usage:  check-lockdown-active.sh [path-to-settings.json]
#         (default: .claude/settings.json relative to current directory)
#
# Exit:
#   0 both Write(.claude/**) and Edit(.claude/**) deny rules present
#   1 one or both missing
#   2 invocation error (missing or malformed settings.json)

set -u

settings="${1:-.claude/settings.json}"

if [ ! -f "$settings" ]; then
  echo "ERROR: settings file not found: $settings" >&2
  exit 2
fi
if ! jq empty "$settings" 2>/dev/null; then
  echo "ERROR: settings file is not valid JSON: $settings" >&2
  exit 2
fi

# Read deny array (may be missing entirely)
deny=$(jq -r '.permissions.deny // [] | .[]' "$settings" 2>/dev/null)

missing=0
for rule in 'Write(.claude/**)' 'Edit(.claude/**)'; do
  if ! echo "$deny" | grep -qFx "$rule"; then
    echo "ERROR: missing deny rule: $rule" >&2
    missing=$((missing+1))
  fi
done

if [ "$missing" -gt 0 ]; then
  echo "FAIL: $missing required deny rule(s) missing in $settings" >&2
  exit 1
fi
echo "OK: lockdown rules present in $settings"
exit 0
