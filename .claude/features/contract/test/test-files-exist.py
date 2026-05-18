#!/usr/bin/env python3
# test-files-exist.py — verify all expected contract feature files exist and scripts are executable.

import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FAIL = 0


def check_file(rel_path):
    global FAIL
    path = os.path.join(FEATURE_DIR, rel_path)
    if not os.path.isfile(path):
        print(f"MISSING FILE: {path}", file=sys.stderr)
        FAIL = 1


def check_exec(rel_path):
    global FAIL
    path = os.path.join(FEATURE_DIR, rel_path)
    if not os.path.isfile(path):
        print(f"MISSING SCRIPT: {path}", file=sys.stderr)
        FAIL = 1
    elif not os.access(path, os.X_OK):
        print(f"NOT EXECUTABLE: {path}", file=sys.stderr)
        FAIL = 1


# feature.json and docs
check_file("feature.json")
check_file("docs/spec/spec.md")
check_file("docs/spec/contract.md")

# Templates
check_file("templates/spec-template.md")
check_file("templates/contract-template.md")
check_file("templates/bug-template.json")
check_file("templates/triage-template.md")
check_file("templates/feature-json-template.json")
check_file("templates/subagent-launch-template.txt")
check_file("templates/project-map-template.json")
check_file("templates/registry-template.json")
check_file("templates/skill-template.md")
check_file("templates/command-template.md")
check_file("templates/handoff-template.md")

# Schemas (4)
check_file("schemas/feature.json.schema.json")
check_file("schemas/registry.json.schema.json")
check_file("schemas/bug.json.schema.json")
check_file("schemas/project-map.json.schema.json")

# Scripts (6) — also check executable
check_exec("scripts/policy-block.py")
check_exec("scripts/dispatch-feature-edit.py")
check_exec("scripts/render-template.py")
check_exec("scripts/check-maps-consistent.py")
check_exec("scripts/rabbit-triage.py")

# find-feature.py and absence of registry.json
import subprocess
result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

ff_path = os.path.join(REPO_ROOT, ".claude/features/contract/scripts/find-feature.py") if REPO_ROOT else ""
if not ff_path or not os.path.isfile(ff_path):
    print("MISSING FILE: find-feature.py", file=sys.stderr)
    FAIL = 1

registry_path = os.path.join(REPO_ROOT, ".claude/features/registry.json") if REPO_ROOT else ""
if registry_path and os.path.isfile(registry_path):
    print("UNEXPECTED FILE: registry.json should not exist (distributed registry design)", file=sys.stderr)
    FAIL = 1

# Validator and enforcement scripts (9)
check_exec("scripts/validate-feature.py")
check_exec("scripts/enforcement/check-no-main-edits.py")
check_exec("scripts/enforcement/check-opus-for-planning-agents.py")
check_exec("scripts/enforcement/check-tests-non-interactive.py")
check_exec("scripts/enforcement/check-sentinel.py")
check_exec("scripts/enforcement/check-naming.py")
check_exec("scripts/enforcement/check-imports-resolve.py")
check_exec("scripts/enforcement/check-symlinks-resolve.py")
check_exec("scripts/enforcement/check-template-schema-producer-consistency.py")

# Tests — check for Python equivalents now
check_exec("test/run.py")
check_file("test/test-files-exist.py")
check_file("test/test-policy-block.py")
check_file("test/test-templates-have-version.py")
check_file("test/test-schemas-valid-json.py")
check_file("test/test-rabbit-triage.py")
check_file("test/test-dispatch.py")
check_file("test/test-build-contract.py")
check_file("test/test-python-only-stack.py")

# dispatch-spec-update artifacts
dsu = os.path.join(FEATURE_DIR, "scripts/dispatch-spec-update.py")
if os.path.isfile(dsu) and os.access(dsu, os.X_OK):
    print("ok: dispatch-spec-update.py exists and is executable")
else:
    print("ko: dispatch-spec-update.py missing or not executable", file=sys.stderr)
    FAIL = 1

spec_update_tmpl = os.path.join(FEATURE_DIR, "templates/spec-update-template.txt")
if os.path.isfile(spec_update_tmpl):
    print("ok: spec-update-template.txt exists")
else:
    print("ko: spec-update-template.txt missing", file=sys.stderr)
    FAIL = 1

dsu_test = os.path.join(FEATURE_DIR, "test/test-dispatch-spec-update.py")
if os.path.isfile(dsu_test):
    print("ok: test-dispatch-spec-update.py exists")
else:
    print("ko: test-dispatch-spec-update.py missing", file=sys.stderr)
    FAIL = 1

# workspace-map artifacts
check_exec("scripts/workspace-map.py")
check_file("schemas/workspace-map.json.schema.json")

if FAIL != 0:
    print("test-files-exist: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-files-exist: all expected files present and scripts executable.")
