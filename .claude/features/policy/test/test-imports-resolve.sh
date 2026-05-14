#!/bin/bash
# test-imports-resolve.sh — assert every @-import in any CLAUDE.md resolves.
set -u
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Find all CLAUDE.md files
mapfile -t claude_mds < <(find "$REPO_ROOT" -name "CLAUDE.md" -not -path "*/archive/*" -not -path "*/.git/*")
for claude_md in "${claude_mds[@]}"; do
  mapfile -t import_paths < <(grep -oE '^@[^[:space:]]+' "$claude_md" 2>/dev/null || true)
  for import_path in "${import_paths[@]}"; do
    # Strip leading @
    resolved="${import_path#@}"
    full="$REPO_ROOT/$resolved"
    if [ -e "$full" ]; then
      ok "$claude_md: $resolved"
    else
      ko "$claude_md: $resolved DOES NOT EXIST"
    fi
  done
done

echo ""
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
