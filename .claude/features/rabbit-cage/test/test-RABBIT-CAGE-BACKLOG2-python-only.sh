#!/usr/bin/env bash
# RABBIT-CAGE-BACKLOG-2: Python-only runtime tech stack
#
# Asserts spec invariants 39 and 40 (post-migration):
#   - No .sh files exist under hooks/ or scripts/ in rabbit-cage.
#   - Every runtime script is a standalone executable Python file
#     with a #!/usr/bin/env python3 shebang.
#   - The expected Python script set from Inv 40 is present and executable.
#   - install.sh is the sole permitted .sh exception (bootstrap entry point).
#   - settings.json and build-contract.json reference .py paths only
#     (for rabbit-cage hooks/scripts), not .sh paths.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CAGE="$REPO_ROOT/.claude/features/rabbit-cage"

fail=0
pass() { echo "  PASS: $*"; }
fail() { echo "  FAIL: $*"; fail=$((fail+1)); }

echo "test-RABBIT-CAGE-BACKLOG2-python-only"
echo ""

# --- 1. No .sh under hooks/ ---
echo "[1] hooks/ contains no .sh files"
sh_in_hooks=$(find "$CAGE/hooks" -maxdepth 1 -type f -name "*.sh" 2>/dev/null)
if [ -z "$sh_in_hooks" ]; then
    pass "no .sh files in hooks/"
else
    fail ".sh files still present in hooks/: $sh_in_hooks"
fi

# --- 2. No .sh under scripts/ ---
echo "[2] scripts/ contains no .sh files"
sh_in_scripts=$(find "$CAGE/scripts" -maxdepth 1 -type f -name "*.sh" 2>/dev/null)
if [ -z "$sh_in_scripts" ]; then
    pass "no .sh files in scripts/"
else
    fail ".sh files still present in scripts/: $sh_in_scripts"
fi

# --- 3. install.sh exception still present at rabbit-cage root ---
echo "[3] install.sh remains at rabbit-cage root (bootstrap exception)"
if [ -f "$CAGE/install.sh" ]; then
    pass "install.sh present (Inv 9 exception)"
else
    fail "install.sh missing at $CAGE/install.sh"
fi

# --- 4. Expected Python runtime scripts exist & are executable ---
echo "[4] Inv 40 Python script set present and executable"
expected_hooks="refresh.py scope-guard.py session-init.py sync-check.py"
expected_scripts="build.py build-targets.py generate-claude-md.py generate-claude-md-header.py new-feature.py rabbit-project.py rabbit-project-consolidate.py rabbit-project-map.py rabbit-project-set-path.py scope-guard-on.py validate-all.py workspace-tree.py"

for f in $expected_hooks; do
    p="$CAGE/hooks/$f"
    if [ -x "$p" ]; then
        pass "executable: hooks/$f"
    else
        fail "missing or non-executable: hooks/$f"
    fi
done

for f in $expected_scripts; do
    p="$CAGE/scripts/$f"
    if [ -x "$p" ]; then
        pass "executable: scripts/$f"
    else
        fail "missing or non-executable: scripts/$f"
    fi
done

# --- 5. Every .py runtime script has #!/usr/bin/env python3 shebang ---
echo "[5] every runtime .py has python3 shebang"
for d in "$CAGE/hooks" "$CAGE/scripts"; do
    while IFS= read -r f; do
        first=$(head -n1 "$f" 2>/dev/null)
        if [ "$first" = "#!/usr/bin/env python3" ]; then
            pass "shebang ok: ${f#$REPO_ROOT/}"
        else
            fail "wrong shebang in ${f#$REPO_ROOT/}: $first"
        fi
    done < <(find "$d" -maxdepth 1 -type f -name "*.py")
done

# --- 6. settings.json hook commands reference .py (not .sh) for rabbit-cage hooks ---
echo "[6] settings.json hook commands invoke .py files"
SETTINGS="$CAGE/settings.json"
if grep -q "\.claude/hooks/.*\.sh" "$SETTINGS"; then
    fail "settings.json still references .sh hook paths:"
    grep -n "\.claude/hooks/.*\.sh" "$SETTINGS" | sed 's/^/    /'
else
    pass "no .sh hook paths in settings.json"
fi
expected_hook_refs="session-init.py refresh.py scope-guard.py sync-check.py"
for h in $expected_hook_refs; do
    if grep -q "\.claude/hooks/$h" "$SETTINGS"; then
        pass "settings.json invokes .claude/hooks/$h"
    else
        fail "settings.json missing reference to .claude/hooks/$h"
    fi
done

# --- 7. build-contract.json copy-file targets reference .py for rabbit-cage hooks ---
echo "[7] build-contract.json copy-file targets reference .py for rabbit-cage hooks"
BC="$REPO_ROOT/.claude/features/contract/build-contract.json"
if [ -f "$BC" ]; then
    bad=$(grep -E "rabbit-cage/(hooks|scripts)/[^\"]+\.sh" "$BC" || true)
    if [ -z "$bad" ]; then
        pass "no rabbit-cage .sh paths in build-contract.json hooks/scripts copy targets"
    else
        fail "build-contract.json still references rabbit-cage .sh files:"
        echo "$bad" | sed 's/^/    /'
    fi
else
    fail "build-contract.json not found at $BC"
fi

echo ""
if [ "$fail" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "FAILED: $fail check(s)"
    exit 1
fi
