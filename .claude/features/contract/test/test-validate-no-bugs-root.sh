#!/bin/bash
# test-validate-no-bugs-root.sh — verify validate-feature.sh handles absence of bugs_root.
#
# t1: exits 0 for a valid feature.json with NO bugs_root field
# t2: exits non-zero for a feature.json missing owner (other required field)

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATE="$FEATURE_DIR/scripts/validate-feature.sh"
FAIL=0

# ---------------------------------------------------------------------------
# Helper: build a minimal valid feature dir without bugs_root
# ---------------------------------------------------------------------------
make_fixture() {
  local dir
  dir="$(mktemp -d)"
  local name
  name="$(basename "$dir")"

  mkdir -p "$dir/docs/spec" "$dir/docs/bugs" "$dir/test"

  cat > "$dir/docs/spec/spec.md" <<'SPEC'
# Minimal spec
Content for test fixture.
SPEC

  cat > "$dir/docs/spec/contract.md" <<'CONTRACT'
# Minimal contract
Content for test fixture.
CONTRACT

  # test/run.sh must exist and be executable
  cat > "$dir/test/run.sh" <<'RUN'
#!/bin/bash
echo "stub run.sh"
RUN
  chmod +x "$dir/test/run.sh"

  cat > "$dir/feature.json" <<JSON
{
  "name": "$name",
  "version": "0.1.0",
  "owner": "test-owner",
  "tdd_state": "spec",
  "summary": "Fixture for test-validate-no-bugs-root.",
  "surface": {
    "hooks": [],
    "commands": [],
    "agents": [],
    "skills": []
  },
  "deprecation_criterion": "when test is done"
}
JSON

  echo "$dir"
}

# ---------------------------------------------------------------------------
# t1: valid feature.json lacking bugs_root — must exit 0
# ---------------------------------------------------------------------------
FIXTURE1="$(make_fixture)"

OUTPUT1="$("$VALIDATE" "$FIXTURE1" 2>&1)"
EXIT1=$?

rm -rf "$FIXTURE1"

if [ "$EXIT1" -ne 0 ]; then
  echo "FAIL t1: validate-feature.sh exited $EXIT1 for feature.json without bugs_root (expected 0)" >&2
  echo "  output: $OUTPUT1" >&2
  FAIL=1
else
  echo "PASS t1: validate-feature.sh exits 0 when bugs_root is absent"
fi

# ---------------------------------------------------------------------------
# t2: feature.json missing 'owner' — must exit non-zero
# ---------------------------------------------------------------------------
FIXTURE2="$(mktemp -d)"
mkdir -p "$FIXTURE2/docs/spec" "$FIXTURE2/docs/bugs" "$FIXTURE2/test"
cat > "$FIXTURE2/docs/spec/spec.md" <<'SPEC'
# Minimal spec
Content.
SPEC
cat > "$FIXTURE2/docs/spec/contract.md" <<'CONTRACT'
# Minimal contract
Content.
CONTRACT
cat > "$FIXTURE2/test/run.sh" <<'RUN'
#!/bin/bash
echo "stub"
RUN
chmod +x "$FIXTURE2/test/run.sh"

FIXTURE2_NAME="$(basename "$FIXTURE2")"
cat > "$FIXTURE2/feature.json" <<JSON
{
  "name": "$FIXTURE2_NAME",
  "version": "0.1.0",
  "tdd_state": "spec",
  "summary": "Fixture missing owner for t2.",
  "surface": {
    "hooks": [],
    "commands": [],
    "agents": [],
    "skills": []
  },
  "deprecation_criterion": "when test is done"
}
JSON

OUTPUT2="$("$VALIDATE" "$FIXTURE2" 2>&1)"
EXIT2=$?

rm -rf "$FIXTURE2"

if [ "$EXIT2" -eq 0 ]; then
  echo "FAIL t2: validate-feature.sh exited 0 for feature.json missing owner (expected non-zero)" >&2
  FAIL=1
else
  echo "PASS t2: validate-feature.sh exits non-zero when owner is missing"
fi

# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------
if [ "$FAIL" -ne 0 ]; then
  echo "test-validate-no-bugs-root: FAIL" >&2
  exit 1
fi

echo "test-validate-no-bugs-root: all checks passed."
