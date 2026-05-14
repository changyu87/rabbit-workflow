#!/bin/bash
# test_python_scripts.sh — TDD tests verifying that bash scripts no longer embed
# python3 heredocs or inline python3 -c calls, and that companion .py files exist.
#
# Affected scripts:
#   find-feature.sh          -> find-feature.py
#   check-maps-consistent.sh -> check-maps-consistent.py
#   render-template.sh       -> render-template.py
#   workspace-map.sh         -> workspace-map.py
#   audit-orphan-storage.sh  -> audit-orphan-storage.py
#   check-template-schema-producer-consistency.sh -> check-template-schema-producer-consistency.py
#
# Exit: 0 all pass; 1 one or more failures.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
SCRIPTS_DIR="$REPO_ROOT/.claude/features/contract/scripts"
ENFORCEMENT_DIR="$SCRIPTS_DIR/enforcement"

PASS=0
FAIL=0

check() {
  local desc="$1"
  local result="$2"
  if [ "$result" = "0" ]; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== test_python_scripts.sh ==="

# --- find-feature ---
echo ""
echo "--- find-feature ---"
check "find-feature.py exists" "$([ -f "$SCRIPTS_DIR/find-feature.py" ] && echo 0 || echo 1)"
check "find-feature.sh has no 'python3 -' heredoc" "$(grep -q "^python3 - " "$SCRIPTS_DIR/find-feature.sh" 2>/dev/null && echo 1 || echo 0)"
check "find-feature.sh has no 'python3 <<' heredoc" "$(grep -q "python3 <<" "$SCRIPTS_DIR/find-feature.sh" 2>/dev/null && echo 1 || echo 0)"
check "find-feature.sh has no inline python3 -c" "$(grep -q "python3 -c " "$SCRIPTS_DIR/find-feature.sh" 2>/dev/null && echo 1 || echo 0)"

# --- check-maps-consistent ---
echo ""
echo "--- check-maps-consistent ---"
check "check-maps-consistent.py exists" "$([ -f "$SCRIPTS_DIR/check-maps-consistent.py" ] && echo 0 || echo 1)"
check "check-maps-consistent.sh has no 'python3 -' heredoc" "$(grep -q "^python3 - " "$SCRIPTS_DIR/check-maps-consistent.sh" 2>/dev/null && echo 1 || echo 0)"
check "check-maps-consistent.sh has no 'python3 <<' heredoc" "$(grep -q "python3 <<" "$SCRIPTS_DIR/check-maps-consistent.sh" 2>/dev/null && echo 1 || echo 0)"
check "check-maps-consistent.sh has no inline python3 -c" "$(grep -q "python3 -c " "$SCRIPTS_DIR/check-maps-consistent.sh" 2>/dev/null && echo 1 || echo 0)"

# --- render-template ---
echo ""
echo "--- render-template ---"
check "render-template.py exists" "$([ -f "$SCRIPTS_DIR/render-template.py" ] && echo 0 || echo 1)"
check "render-template.sh has no 'python3 -' heredoc" "$(grep -q "^python3 - " "$SCRIPTS_DIR/render-template.sh" 2>/dev/null && echo 1 || echo 0)"
check "render-template.sh has no 'python3 <<' heredoc" "$(grep -q "python3 <<" "$SCRIPTS_DIR/render-template.sh" 2>/dev/null && echo 1 || echo 0)"
check "render-template.sh has no inline python3 -c" "$(grep -q "python3 -c " "$SCRIPTS_DIR/render-template.sh" 2>/dev/null && echo 1 || echo 0)"

# --- workspace-map ---
echo ""
echo "--- workspace-map ---"
check "workspace-map.py exists" "$([ -f "$SCRIPTS_DIR/workspace-map.py" ] && echo 0 || echo 1)"
check "workspace-map.sh has no 'python3 <<' heredoc" "$(grep -q "python3 <<" "$SCRIPTS_DIR/workspace-map.sh" 2>/dev/null && echo 1 || echo 0)"
check "workspace-map.sh has no inline python3 -c" "$(grep -q "python3 -c " "$SCRIPTS_DIR/workspace-map.sh" 2>/dev/null && echo 1 || echo 0)"

# --- audit-orphan-storage ---
echo ""
echo "--- audit-orphan-storage ---"
check "audit-orphan-storage.py exists" "$([ -f "$SCRIPTS_DIR/audit-orphan-storage.py" ] && echo 0 || echo 1)"
check "audit-orphan-storage.sh has no 'python3 -' heredoc" "$(grep -q "^python3 - " "$SCRIPTS_DIR/audit-orphan-storage.sh" 2>/dev/null && echo 1 || echo 0)"
check "audit-orphan-storage.sh has no 'python3 <<' heredoc" "$(grep -q "python3 <<" "$SCRIPTS_DIR/audit-orphan-storage.sh" 2>/dev/null && echo 1 || echo 0)"
check "audit-orphan-storage.sh has no inline python3 -c" "$(grep -q "python3 -c " "$SCRIPTS_DIR/audit-orphan-storage.sh" 2>/dev/null && echo 1 || echo 0)"

# --- check-template-schema-producer-consistency ---
echo ""
echo "--- check-template-schema-producer-consistency ---"
check "check-template-schema-producer-consistency.py exists" "$([ -f "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.py" ] && echo 0 || echo 1)"
check "check-template-schema-producer-consistency.sh has no 'python3 -' heredoc" "$(grep -q "^python3 - " "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" 2>/dev/null && echo 1 || echo 0)"
check "check-template-schema-producer-consistency.sh has no 'python3 <<' heredoc" "$(grep -q "python3 <<" "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" 2>/dev/null && echo 1 || echo 0)"
check "check-template-schema-producer-consistency.sh has no inline python3 -c" "$(grep -q "python3 -c " "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" 2>/dev/null && echo 1 || echo 0)"

echo ""
echo "=== Results: $PASS pass, $FAIL fail ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
