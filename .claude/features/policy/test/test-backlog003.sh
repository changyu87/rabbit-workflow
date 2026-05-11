#!/usr/bin/env bash
# test-backlog003.sh — Verify coding-rules.md uses standalone numbering (1-5) and clean heading.
# BACKLOG-003: coding-rules.md should renumber rules 1-5 and drop 'Part II' from heading.
set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODING_RULES="$FEATURE_DIR/coding-rules.md"

FAILURES=0

# --- Group A: Rule numbering ---

# t1: must NOT contain '### 4. Think Before Coding' (old cross-file numbering gone)
if grep -q '### 4\. Think Before Coding' "$CODING_RULES"; then
  echo "FAIL: t1: coding-rules.md should NOT contain '### 4. Think Before Coding' (cross-file numbering)"
  FAILURES=$((FAILURES + 1))
else
  echo "PASS: t1: coding-rules.md does not contain '### 4. Think Before Coding'"
fi

# t2: must contain '## 1.' (first rule starts at 1, promoted to H2)
if grep -qE '^## 1\.' "$CODING_RULES"; then
  echo "PASS: t2: coding-rules.md contains '## 1.'"
else
  echo "FAIL: t2: coding-rules.md should contain '## 1.' (rules start at 1)"
  FAILURES=$((FAILURES + 1))
fi

# t3: must NOT contain '### 6.' (confirms rules stop at 5; six rules would mean old cross-numbering remnant)
if grep -q '### 6\.' "$CODING_RULES"; then
  echo "FAIL: t3: coding-rules.md should NOT contain '### 6.' (rules must stop at 5)"
  FAILURES=$((FAILURES + 1))
else
  echo "PASS: t3: coding-rules.md does not contain '### 6.' (rules stop at 5)"
fi

# t4: must NOT contain '### 8.' (old last rule gone)
if grep -q '### 8\.' "$CODING_RULES"; then
  echo "FAIL: t4: coding-rules.md should NOT contain '### 8.' (old numbering)"
  FAILURES=$((FAILURES + 1))
else
  echo "PASS: t4: coding-rules.md does not contain '### 8.'"
fi

# --- Group B: Part II heading ---

# t5: must NOT contain 'Part II'
if grep -q 'Part II' "$CODING_RULES"; then
  echo "FAIL: t5: coding-rules.md should NOT contain 'Part II'"
  FAILURES=$((FAILURES + 1))
else
  echo "PASS: t5: coding-rules.md does not contain 'Part II'"
fi

# t6: must NOT contain '## Code-Editing Discipline' (heading removed in restructure)
if grep -q '^## Code-Editing Discipline$' "$CODING_RULES"; then
  echo "FAIL: t6: coding-rules.md should NOT contain '## Code-Editing Discipline' (heading removed)"
  FAILURES=$((FAILURES + 1))
else
  echo "PASS: t6: coding-rules.md does not contain '## Code-Editing Discipline'"
fi

# --- Summary ---
echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo "All tests passed."
  exit 0
else
  echo "$FAILURES test(s) failed."
  exit 1
fi
