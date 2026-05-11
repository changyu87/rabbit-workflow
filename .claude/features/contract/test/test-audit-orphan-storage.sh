#!/bin/bash
# test-audit-orphan-storage.sh — verify audit-orphan-storage.sh behavior.
#
# t3: script exists at scripts/audit-orphan-storage.sh and is executable
# t4: exits 0 and prints no ORPHAN lines when all subdirs match known features
# t5: exits non-zero and prints ORPHAN when an unknown subdir is present

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT="$FEATURE_DIR/scripts/audit-orphan-storage.sh"
FAIL=0

# ---------------------------------------------------------------------------
# t3: script exists and is executable
# ---------------------------------------------------------------------------
if [ ! -f "$AUDIT" ]; then
  echo "FAIL t3: audit-orphan-storage.sh does not exist at $AUDIT" >&2
  FAIL=1
elif [ ! -x "$AUDIT" ]; then
  echo "FAIL t3: audit-orphan-storage.sh is not executable: $AUDIT" >&2
  FAIL=1
else
  echo "PASS t3: audit-orphan-storage.sh exists and is executable"
fi

# If the script doesn't exist, t4 and t5 cannot run meaningfully.
if [ ! -x "$AUDIT" ]; then
  echo "test-audit-orphan-storage: FAIL (t3 failed; skipping t4, t5)" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Shared setup: a registry with two known feature names
# ---------------------------------------------------------------------------
REGISTRY_DIR="$(mktemp -d)"
cat > "$REGISTRY_DIR/registry.json" <<'JSON'
{
  "schema_version": "1.0.0",
  "owner": "test",
  "features": {
    "feature-alpha": {
      "name": "feature-alpha",
      "version": "0.1.0",
      "owner": "test",
      "tdd_state": "spec",
      "summary": "Test feature alpha",
      "path": ".claude/features/feature-alpha"
    },
    "feature-beta": {
      "name": "feature-beta",
      "version": "0.1.0",
      "owner": "test",
      "tdd_state": "spec",
      "summary": "Test feature beta",
      "path": ".claude/features/feature-beta"
    }
  }
}
JSON

# ---------------------------------------------------------------------------
# t4: all subdirs in temp bugs/backlogs match known features — exits 0, no ORPHAN
# ---------------------------------------------------------------------------
BUGS4="$(mktemp -d)"
BACKLOGS4="$(mktemp -d)"
mkdir -p "$BUGS4/feature-alpha" "$BUGS4/feature-beta"
mkdir -p "$BACKLOGS4/feature-alpha"

OUTPUT4="$("$AUDIT" \
  --bugs-root "$BUGS4" \
  --backlogs-root "$BACKLOGS4" \
  --registry "$REGISTRY_DIR/registry.json" \
  2>&1)"
EXIT4=$?

rm -rf "$BUGS4" "$BACKLOGS4"

if [ "$EXIT4" -ne 0 ]; then
  echo "FAIL t4: audit-orphan-storage.sh exited $EXIT4 for all-known dirs (expected 0)" >&2
  echo "  output: $OUTPUT4" >&2
  FAIL=1
elif echo "$OUTPUT4" | grep -q "ORPHAN"; then
  echo "FAIL t4: audit-orphan-storage.sh printed ORPHAN when none expected" >&2
  echo "  output: $OUTPUT4" >&2
  FAIL=1
else
  echo "PASS t4: audit-orphan-storage.sh exits 0 and prints no ORPHAN for known dirs"
fi

# ---------------------------------------------------------------------------
# t5: one unknown subdir present — exits non-zero and prints ORPHAN
# ---------------------------------------------------------------------------
BUGS5="$(mktemp -d)"
BACKLOGS5="$(mktemp -d)"
mkdir -p "$BUGS5/feature-alpha"
mkdir -p "$BUGS5/unknown-mystery-feature"   # orphan

OUTPUT5="$("$AUDIT" \
  --bugs-root "$BUGS5" \
  --backlogs-root "$BACKLOGS5" \
  --registry "$REGISTRY_DIR/registry.json" \
  2>&1)"
EXIT5=$?

rm -rf "$BUGS5" "$BACKLOGS5"

if [ "$EXIT5" -eq 0 ]; then
  echo "FAIL t5: audit-orphan-storage.sh exited 0 when orphan present (expected non-zero)" >&2
  echo "  output: $OUTPUT5" >&2
  FAIL=1
elif ! echo "$OUTPUT5" | grep -q "ORPHAN"; then
  echo "FAIL t5: audit-orphan-storage.sh did not print ORPHAN when orphan present" >&2
  echo "  output: $OUTPUT5" >&2
  FAIL=1
else
  echo "PASS t5: audit-orphan-storage.sh exits non-zero and prints ORPHAN for unknown subdir"
fi

# ---------------------------------------------------------------------------
# Cleanup shared registry dir
# ---------------------------------------------------------------------------
rm -rf "$REGISTRY_DIR"

# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------
if [ "$FAIL" -ne 0 ]; then
  echo "test-audit-orphan-storage: FAIL" >&2
  exit 1
fi

echo "test-audit-orphan-storage: all checks passed."
