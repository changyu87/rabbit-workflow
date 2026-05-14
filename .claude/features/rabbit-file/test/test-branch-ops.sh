#!/usr/bin/env bash
# test-branch-ops.sh — run pytest for branch_ops.py
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m pytest "$SCRIPT_DIR/test-branch-ops.py" -v 2>&1
