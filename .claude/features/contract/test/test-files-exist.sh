#!/bin/bash
# test-files-exist.sh — verify all expected contract feature files exist and scripts are executable.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

check_file() {
  local path="$FEATURE_DIR/$1"
  if [ ! -f "$path" ]; then
    echo "MISSING FILE: $path" >&2
    FAIL=1
  fi
}

check_exec() {
  local path="$FEATURE_DIR/$1"
  if [ ! -f "$path" ]; then
    echo "MISSING SCRIPT: $path" >&2
    FAIL=1
  elif [ ! -x "$path" ]; then
    echo "NOT EXECUTABLE: $path" >&2
    FAIL=1
  fi
}

# feature.json and docs
check_file "feature.json"
check_file "docs/spec/spec.md"
check_file "docs/spec/contract.md"

# Templates (8)
check_file "templates/spec-template.md"
check_file "templates/contract-template.md"
check_file "templates/bug-template.json"
check_file "templates/triage-template.md"
check_file "templates/feature-json-template.json"
check_file "templates/subagent-launch-template.txt"
check_file "templates/project-map-template.json"
check_file "templates/registry-template.json"

# Schemas (4)
check_file "schemas/feature.json.schema.json"
check_file "schemas/registry.json.schema.json"
check_file "schemas/bug.json.schema.json"
check_file "schemas/project-map.json.schema.json"

# Scripts (7) — also check executable
check_exec "scripts/policy-block.sh"
check_exec "scripts/dispatch-feature-edit.sh"
check_exec "scripts/rebuild-registry.sh"
check_exec "scripts/relink.sh"
check_exec "scripts/render-template.sh"
check_exec "scripts/check-maps-consistent.sh"
check_exec "scripts/rabbit-triage.sh"

# Validator and enforcement scripts (9)
check_exec "scripts/validate-feature.sh"
check_exec "scripts/enforcement/check-no-main-edits.sh"
check_exec "scripts/enforcement/check-opus-for-planning-agents.sh"
check_exec "scripts/enforcement/check-tests-non-interactive.sh"
check_exec "scripts/enforcement/check-sentinel.sh"
check_exec "scripts/enforcement/check-naming.sh"
check_exec "scripts/enforcement/check-imports-resolve.sh"
check_exec "scripts/enforcement/check-symlinks-resolve.sh"
check_exec "scripts/enforcement/check-template-schema-producer-consistency.sh"

# Tests (5)
check_exec "test/run.sh"
check_file "test/test-files-exist.sh"
check_file "test/test-policy-block.sh"
check_file "test/test-templates-have-version.sh"
check_file "test/test-schemas-valid-json.sh"
check_file "test/test-rabbit-triage.sh"
check_file "test/test-dispatch.sh"
check_file "test/test-relink.sh"

# dispatch-spec-update artifacts
[ -f "$FEATURE_DIR/scripts/dispatch-spec-update.sh" ] && \
  [ -x "$FEATURE_DIR/scripts/dispatch-spec-update.sh" ] \
  && echo "ok: dispatch-spec-update.sh exists and is executable" \
  || { echo "ko: dispatch-spec-update.sh missing or not executable" >&2; FAIL=1; }

[ -f "$FEATURE_DIR/templates/spec-update-template.txt" ] \
  && echo "ok: spec-update-template.txt exists" \
  || { echo "ko: spec-update-template.txt missing" >&2; FAIL=1; }

[ -f "$FEATURE_DIR/test/test-dispatch-spec-update.sh" ] \
  && echo "ok: test-dispatch-spec-update.sh exists" \
  || { echo "ko: test-dispatch-spec-update.sh missing" >&2; FAIL=1; }

if [ $FAIL -ne 0 ]; then
  echo "test-files-exist: FAIL" >&2
  exit 1
fi

echo "test-files-exist: all expected files present and scripts executable."
