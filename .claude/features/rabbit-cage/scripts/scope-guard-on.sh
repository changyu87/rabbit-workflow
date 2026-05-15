#!/usr/bin/env bash
# scope-guard-on.sh — Revoke the scope-guard override, re-arming the default-deny.
#
# Removes .rabbit-scope-override (if present) so scope-guard.sh returns to its
# default-deny posture. This is the canonical answer to "scope guard back on" /
# "revoke the session override".
#
# Usage:
#   bash .claude/features/rabbit-cage/scripts/scope-guard-on.sh
#
# Behaviour:
#   - If .rabbit-scope-override exists: deletes it and prints a confirmation.
#   - If .rabbit-scope-override is absent: no-op, exits 0.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code exposes a native scope-override mechanism.

set -euo pipefail

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"
OVERRIDE_FILE="$REPO_ROOT/.rabbit-scope-override"

if [ -f "$OVERRIDE_FILE" ]; then
    rm -f "$OVERRIDE_FILE"
    echo "[rabbit] Scope guard re-armed — .rabbit-scope-override removed."
else
    echo "[rabbit] Scope guard is already on — no active override to revoke."
fi

exit 0
