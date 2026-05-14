#!/usr/bin/env bash
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Running test-item-status.py..."
python3 -m pytest "$SCRIPT_DIR/test-item-status.py" -v
