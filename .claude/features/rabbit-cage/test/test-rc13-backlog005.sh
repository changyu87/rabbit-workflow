#!/usr/bin/env bash
# test-rc13-backlog005.sh
# Tests for RABBIT-CAGE-13 (rabbit-workspace skill → command) and BACKLOG-005 (rabbit-project clarification)
# R3-compliant: no interactive constructs (no read, no select)
# Fails against current state; passes after the fix is applied.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
FEATURE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"

FAILURES=0

# ---------------------------------------------------------------------------
# RABBIT-CAGE-13 tests
# ---------------------------------------------------------------------------

# t1: commands/rabbit-workspace.md exists at the expected path
EXPECTED_CMD="$FEATURE_DIR/commands/rabbit-workspace.md"
if [ -f "$EXPECTED_CMD" ]; then
  echo "  PASS t1: commands/rabbit-workspace.md exists"
else
  echo "  FAIL t1: commands/rabbit-workspace.md does NOT exist (expected: $EXPECTED_CMD)"
  FAILURES=$((FAILURES + 1))
fi

# t2: commands/rabbit-workspace.md references workspace-tree.sh
if [ -f "$EXPECTED_CMD" ] && grep -q "workspace-tree.sh" "$EXPECTED_CMD"; then
  echo "  PASS t2: commands/rabbit-workspace.md references workspace-tree.sh"
else
  echo "  FAIL t2: commands/rabbit-workspace.md does not contain 'workspace-tree.sh'"
  FAILURES=$((FAILURES + 1))
fi

# t3: skills/rabbit-workspace/ directory does NOT exist
SKILL_DIR="$FEATURE_DIR/skills/rabbit-workspace"
if [ ! -d "$SKILL_DIR" ]; then
  echo "  PASS t3: skills/rabbit-workspace/ directory does not exist"
else
  echo "  FAIL t3: skills/rabbit-workspace/ directory still exists (should be retired)"
  FAILURES=$((FAILURES + 1))
fi

# t4: feature.json surface.skills does NOT contain "rabbit-workspace"
FEATURE_JSON="$FEATURE_DIR/feature.json"
if grep -q '"skills"' "$FEATURE_JSON" && grep -A 20 '"skills"' "$FEATURE_JSON" | grep -q '"rabbit-workspace"'; then
  echo "  FAIL t4: feature.json surface.skills still contains 'rabbit-workspace'"
  FAILURES=$((FAILURES + 1))
else
  echo "  PASS t4: feature.json surface.skills does not contain 'rabbit-workspace'"
fi

# t5: feature.json surface.commands contains a string matching "rabbit-workspace.md"
if grep -q "rabbit-workspace.md" "$FEATURE_JSON"; then
  echo "  PASS t5: feature.json surface.commands contains 'rabbit-workspace.md'"
else
  echo "  FAIL t5: feature.json surface.commands does NOT contain 'rabbit-workspace.md'"
  FAILURES=$((FAILURES + 1))
fi

# ---------------------------------------------------------------------------
# BACKLOG-005 tests
# ---------------------------------------------------------------------------

# t6: rabbit-project.md contains the phrase "not a status command" (case-insensitive)
RABBIT_PROJECT_MD="$FEATURE_DIR/commands/rabbit-project.md"
if grep -qi "not a status command" "$RABBIT_PROJECT_MD"; then
  echo "  PASS t6: rabbit-project.md contains 'not a status command'"
else
  echo "  FAIL t6: rabbit-project.md does NOT contain 'not a status command'"
  FAILURES=$((FAILURES + 1))
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo "All tests passed."
  exit 0
else
  echo "$FAILURES test(s) failed."
  exit 1
fi
