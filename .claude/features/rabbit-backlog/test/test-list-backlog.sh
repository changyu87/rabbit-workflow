#!/usr/bin/env bash
# test-list-backlog.sh — tests for list-backlog.sh (lists backlog items with filtering).
#
# Tests verify:
#   t1: list-backlog.sh exists and is executable
#   t2: default output is a valid JSON array
#   t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line
#   t4: --status filter returns only items with matching status
#   t5: --feature filter returns only items from named feature
#   t6: --feature with comma-separated values returns items from all named features
#   t7: --status with no matches outputs [] (JSON) or "(no items)" (text)
#   t8: -h/--help exits 0

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="${REPO_ROOT}/.claude/features/rabbit-backlog"
SCRIPTS_DIR="${FEATURE_DIR}/scripts"

LIST_BACKLOG="${SCRIPTS_DIR}/list-backlog.sh"

pass=0
fail=0

ok() {
    echo "  PASS  $1"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL  $1${2:+ -- $2}"
    fail=$((fail + 1))
}

echo "=== test-list-backlog.sh: list-backlog.sh spec behaviors ==="
echo ""

# t1: list-backlog.sh exists and is executable
if [ -x "$LIST_BACKLOG" ]; then
    ok "t1: list-backlog.sh exists and is executable"
else
    fail_t "t1: list-backlog.sh exists and is executable" \
           "not found or not executable: $LIST_BACKLOG"
fi

# Isolated environment with fake backlog items for testing filters and output.
ISO_REPO="$(mktemp -d)"
trap 'rm -rf "$ISO_REPO"' EXIT

mkdir -p "$ISO_REPO/.claude/backlogs/feature-alpha/FEATURE-ALPHA-BACKLOG-1"
mkdir -p "$ISO_REPO/.claude/backlogs/feature-alpha/FEATURE-ALPHA-BACKLOG-2"
mkdir -p "$ISO_REPO/.claude/backlogs/feature-beta/FEATURE-BETA-BACKLOG-1"

cat > "$ISO_REPO/.claude/backlogs/feature-alpha/FEATURE-ALPHA-BACKLOG-1/item.json" <<'EOF'
{
  "name": "FEATURE-ALPHA-BACKLOG-1",
  "title": "Alpha item one",
  "status": "open",
  "priority": "high",
  "description": "",
  "owner": "tester",
  "filed": "2026-05-12T00:00:00Z",
  "filed_by": "tester",
  "closed": null,
  "fix_commits": [],
  "history": []
}
EOF

cat > "$ISO_REPO/.claude/backlogs/feature-alpha/FEATURE-ALPHA-BACKLOG-2/item.json" <<'EOF'
{
  "name": "FEATURE-ALPHA-BACKLOG-2",
  "title": "Alpha item two",
  "status": "in-progress",
  "priority": "medium",
  "description": "",
  "owner": "tester",
  "filed": "2026-05-12T00:00:00Z",
  "filed_by": "tester",
  "closed": null,
  "fix_commits": [],
  "history": []
}
EOF

cat > "$ISO_REPO/.claude/backlogs/feature-beta/FEATURE-BETA-BACKLOG-1/item.json" <<'EOF'
{
  "name": "FEATURE-BETA-BACKLOG-1",
  "title": "Beta item one",
  "status": "implemented",
  "priority": "low",
  "description": "",
  "owner": "tester",
  "filed": "2026-05-12T00:00:00Z",
  "filed_by": "tester",
  "closed": "2026-05-12T01:00:00Z",
  "fix_commits": ["abc123"],
  "history": []
}
EOF

# Copy list-backlog.sh into isolated environment so RABBIT_ROOT can be set
ISO_SCRIPTS_DIR="$ISO_REPO/scripts"
mkdir -p "$ISO_SCRIPTS_DIR"
if [ -x "$LIST_BACKLOG" ]; then
    cp "$LIST_BACKLOG" "$ISO_SCRIPTS_DIR/list-backlog.sh"
    chmod +x "$ISO_SCRIPTS_DIR/list-backlog.sh"
fi
ISO_LIST_BACKLOG="$ISO_SCRIPTS_DIR/list-backlog.sh"

# t2: default output is a valid JSON array containing all items
if [ -x "$ISO_LIST_BACKLOG" ]; then
    out="$(RABBIT_ROOT="$ISO_REPO" bash "$ISO_LIST_BACKLOG" 2>&1)"
    if echo "$out" | jq -e 'type == "array"' >/dev/null 2>&1; then
        count="$(echo "$out" | jq 'length')"
        if [ "$count" -eq 3 ]; then
            ok "t2: default output is a valid JSON array with all items (count=$count)"
        else
            fail_t "t2: default output is a valid JSON array with all items" \
                   "expected 3 items, got $count"
        fi
    else
        fail_t "t2: default output is a valid JSON array with all items" \
               "output is not valid JSON array: $out"
    fi
else
    fail_t "t2: default output is a valid JSON array with all items" \
           "list-backlog.sh not executable"
fi

# t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line
if [ -x "$ISO_LIST_BACKLOG" ]; then
    out="$(RABBIT_ROOT="$ISO_REPO" bash "$ISO_LIST_BACKLOG" --text 2>&1)"
    # Expect lines matching: NAME  [STATUS]  [PRIORITY]  TITLE
    if echo "$out" | grep -qE '^\S+  \[[^]]+\]  \[[^]]+\]  .+$'; then
        # Verify each item line has 3 space-separated bracketed fields
        if echo "$out" | grep -qE 'FEATURE-ALPHA-BACKLOG-1  \[open\]  \[high\]  Alpha item one'; then
            ok "t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line"
        else
            fail_t "t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line" \
                   "expected 'FEATURE-ALPHA-BACKLOG-1  [open]  [high]  Alpha item one' in output; got: $out"
        fi
    else
        fail_t "t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line" \
               "output lines do not match expected format; got: $out"
    fi
else
    fail_t "t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line" \
           "list-backlog.sh not executable"
fi

# t4: --status filter returns only items with matching status
if [ -x "$ISO_LIST_BACKLOG" ]; then
    out="$(RABBIT_ROOT="$ISO_REPO" bash "$ISO_LIST_BACKLOG" --status open 2>&1)"
    if echo "$out" | jq -e 'type == "array"' >/dev/null 2>&1; then
        count="$(echo "$out" | jq 'length')"
        non_open="$(echo "$out" | jq '[.[] | select(.status != "open")] | length')"
        if [ "$count" -eq 1 ] && [ "$non_open" -eq 0 ]; then
            ok "t4: --status open returns only open items (count=$count)"
        else
            fail_t "t4: --status open returns only open items" \
                   "expected 1 open item with 0 non-open, got count=$count non_open=$non_open; out=$out"
        fi
    else
        fail_t "t4: --status open returns only open items" \
               "output is not valid JSON array: $out"
    fi
else
    fail_t "t4: --status open returns only open items" \
           "list-backlog.sh not executable"
fi

# t5: --feature filter returns only items from named feature
if [ -x "$ISO_LIST_BACKLOG" ]; then
    out="$(RABBIT_ROOT="$ISO_REPO" bash "$ISO_LIST_BACKLOG" --feature feature-beta 2>&1)"
    if echo "$out" | jq -e 'type == "array"' >/dev/null 2>&1; then
        count="$(echo "$out" | jq 'length')"
        names="$(echo "$out" | jq -r '.[].name')"
        if [ "$count" -eq 1 ] && echo "$names" | grep -q "FEATURE-BETA-BACKLOG-1"; then
            ok "t5: --feature feature-beta returns only beta items (count=$count)"
        else
            fail_t "t5: --feature feature-beta returns only beta items" \
                   "expected 1 item with FEATURE-BETA-BACKLOG-1, got count=$count names=$names"
        fi
    else
        fail_t "t5: --feature feature-beta returns only beta items" \
               "output is not valid JSON array: $out"
    fi
else
    fail_t "t5: --feature feature-beta returns only beta items" \
           "list-backlog.sh not executable"
fi

# t6: --feature with comma-separated values returns items from all named features
if [ -x "$ISO_LIST_BACKLOG" ]; then
    out="$(RABBIT_ROOT="$ISO_REPO" bash "$ISO_LIST_BACKLOG" --feature feature-alpha,feature-beta 2>&1)"
    if echo "$out" | jq -e 'type == "array"' >/dev/null 2>&1; then
        count="$(echo "$out" | jq 'length')"
        if [ "$count" -eq 3 ]; then
            ok "t6: --feature with comma-separated values returns items from all named features (count=$count)"
        else
            fail_t "t6: --feature with comma-separated values returns items from all named features" \
                   "expected 3 items, got $count; out=$out"
        fi
    else
        fail_t "t6: --feature with comma-separated values returns items from all named features" \
               "output is not valid JSON array: $out"
    fi
else
    fail_t "t6: --feature with comma-separated values returns items from all named features" \
           "list-backlog.sh not executable"
fi

# t7: --status with no matches outputs [] (JSON mode)
if [ -x "$ISO_LIST_BACKLOG" ]; then
    out="$(RABBIT_ROOT="$ISO_REPO" bash "$ISO_LIST_BACKLOG" --status reopened 2>&1)"
    if [ "$out" = "[]" ]; then
        ok "t7: --status reopened (no matches) outputs [] in JSON mode"
    else
        fail_t "t7: --status reopened (no matches) outputs [] in JSON mode" \
               "expected '[]', got: $out"
    fi
else
    fail_t "t7: --status reopened (no matches) outputs [] in JSON mode" \
           "list-backlog.sh not executable"
fi

# t8: -h/--help exits 0
if [ -x "$LIST_BACKLOG" ]; then
    if bash "$LIST_BACKLOG" --help >/dev/null 2>&1; then
        ok "t8: --help exits 0"
    else
        fail_t "t8: --help exits 0" "exited non-zero"
    fi
else
    fail_t "t8: --help exits 0" "list-backlog.sh not executable"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
