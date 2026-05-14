#!/bin/bash
# check-maps-consistent.sh — verify registry and filesystem are in sync.
#
# Usage:
#   check-maps-consistent.sh <features-dir>
#
# Verifies that every directory under <features-dir> containing a feature.json
# is listed in <features-dir>/registry.json, and vice versa.
#
# Exit:
#   0 consistent
#   1 inconsistency found (descriptive error printed to stderr)
#   2 invocation error
#
# Version: 1.1.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when registry.json is replaced by a native feature index.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -ne 1 ]; then
  echo "ERROR: usage: check-maps-consistent.sh <features-dir>" >&2
  exit 2
fi

FEATURES_DIR="$1"

if [ ! -d "$FEATURES_DIR" ]; then
  echo "ERROR: features-dir does not exist: $FEATURES_DIR" >&2
  exit 2
fi

REGISTRY="$FEATURES_DIR/registry.json"

if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: registry.json not found: $REGISTRY" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required" >&2
  exit 1
fi

python3 "$SCRIPT_DIR/check-maps-consistent.py" "$FEATURES_DIR" "$REGISTRY"
