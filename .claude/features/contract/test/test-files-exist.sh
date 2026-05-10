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

# Validator and enforcement scripts (6)
check_exec "scripts/validate-feature.sh"
check_exec "scripts/enforcement/check-no-main-edits.sh"
check_exec "scripts/enforcement/check-opus-for-planning-agents.sh"
check_exec "scripts/enforcement/check-tests-non-interactive.sh"
check_exec "scripts/enforcement/check-sentinel.sh"
check_exec "scripts/enforcement/check-naming.sh"

# Tests (5)
check_exec "test/run.sh"
check_file "test/test-files-exist.sh"
check_file "test/test-policy-block.sh"
check_file "test/test-templates-have-version.sh"
check_file "test/test-schemas-valid-json.sh"
check_file "test/test-rabbit-triage.sh"
check_file "test/test-dispatch.sh"
check_file "test/test-relink.sh"

if [ $FAIL -ne 0 ]; then
  echo "test-files-exist: FAIL" >&2
  exit 1
fi

echo "test-files-exist: all expected files present and scripts executable."
