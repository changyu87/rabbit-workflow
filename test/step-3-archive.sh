#!/usr/bin/env bash
# test/step-3-archive.sh
# Verifies step-3 archive migration for the 2026-05-09 pre-redesign snapshot.
# Non-interactive; exits 0 on success, non-zero on first failure.
set -euo pipefail

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null)}"
ARCHIVE="${REPO_ROOT}/archive/2026-05-09-pre-redesign"
FEATURES="${REPO_ROOT}/.claude/features"

pass() { printf "PASS  %s\n" "$1"; }
fail() { printf "FAIL  %s\n" "$1"; exit 1; }

# 1. Archive dirs exist and are non-empty
for dir in vet breeder subagent-policy-injection; do
    target="${ARCHIVE}/features/${dir}"
    if [ -d "$target" ] && [ -n "$(ls -A "$target")" ]; then
        pass "archive/features/${dir} exists and is non-empty"
    else
        fail "archive/features/${dir} missing or empty"
    fi
done

# 2. Source dirs no longer exist
for dir in vet breeder subagent-policy-injection; do
    src="${FEATURES}/${dir}"
    if [ ! -e "$src" ]; then
        pass ".claude/features/${dir} has been removed"
    else
        fail ".claude/features/${dir} still exists (should have been deleted)"
    fi
done

# 3. README exists
readme="${ARCHIVE}/README.md"
if [ -f "$readme" ]; then
    pass "archive/2026-05-09-pre-redesign/README.md exists"
else
    fail "archive/2026-05-09-pre-redesign/README.md missing"
fi

echo ""
echo "All checks passed."
