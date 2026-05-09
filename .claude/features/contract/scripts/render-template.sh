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

set -u

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

# Build substitution pairs from remaining args.
declare -A SUBS
for pair in "$@"; do
  key="${pair%%=*}"
  val="${pair#*=}"
  SUBS["$key"]="$val"
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required" >&2
  exit 1
fi

# Pass substitutions via stdin as JSON so we avoid shell quoting hazards.
SUBS_JSON="{"
first=1
for key in "${!SUBS[@]}"; do
  val="${SUBS[$key]}"
  # Escape special characters for JSON.
  escaped_val="$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$val")"
  if [ $first -eq 1 ]; then
    SUBS_JSON+="\"$key\": $escaped_val"
    first=0
  else
    SUBS_JSON+=", \"$key\": $escaped_val"
  fi
done
SUBS_JSON+="}"

python3 - "$TEMPLATE" "$OUTPUT" "$SUBS_JSON" <<'PYEOF'
import json
import re
import sys

template_path = sys.argv[1]
output_path = sys.argv[2]
subs = json.loads(sys.argv[3])

with open(template_path) as f:
    content = f.read()

for key, val in subs.items():
    content = content.replace("{{" + key + "}}", val)

with open(output_path, "w") as f:
    f.write(content)

print(f"Rendered: {template_path} -> {output_path}")
PYEOF
