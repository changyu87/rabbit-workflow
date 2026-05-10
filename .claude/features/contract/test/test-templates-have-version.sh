#!/bin/bash
# test-templates-have-version.sh — verify every template file carries a template_version marker.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATES_DIR="$FEATURE_DIR/templates"
FAIL=0

for tmpl in "$TEMPLATES_DIR"/*.md "$TEMPLATES_DIR"/*.json "$TEMPLATES_DIR"/*.txt; do
  [ -f "$tmpl" ] || continue
  if ! grep -qF "template_version" "$tmpl"; then
    echo "FAIL: missing 'template_version' in: $tmpl" >&2
    FAIL=1
  fi
done

if [ $FAIL -ne 0 ]; then
  echo "test-templates-have-version: FAIL" >&2
  exit 1
fi

echo "test-templates-have-version: all template files contain 'template_version'."
