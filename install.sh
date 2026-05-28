#!/usr/bin/env bash
# install.sh — install rabbit into the current project as .rabbit/
#
# One-liner usage:
#   curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
#
# Or download + run:
#   curl -fsSLO https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh && bash install.sh
#
# Env vars:
#   RABBIT_REPO  — default changyu87/rabbit-workflow
#   RABBIT_REF   — default main (branch, tag, or SHA)

set -euo pipefail

RABBIT_REPO="${RABBIT_REPO:-changyu87/rabbit-workflow}"
RABBIT_REF="${RABBIT_REF:-main}"

# Pre-flight
for cmd in python3 curl tar; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: $cmd is required but not found in PATH" >&2; exit 1; }
done

# Refuse if .rabbit/ already exists
if [ -d .rabbit ]; then
  echo "error: .rabbit/ already exists in $(pwd)" >&2
  echo "       to update an existing install, see the manual update procedure" >&2
  exit 1
fi

# Download and extract
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

ARCHIVE_URL="https://github.com/${RABBIT_REPO}/archive/${RABBIT_REF}.tar.gz"
echo "Fetching ${RABBIT_REPO}@${RABBIT_REF}..."
curl -fsSL "$ARCHIVE_URL" -o "$TMP/rabbit.tar.gz" || {
  echo "error: download failed from $ARCHIVE_URL" >&2
  exit 1
}
tar -xzf "$TMP/rabbit.tar.gz" -C "$TMP"

# Locate extracted source dir (GitHub names it rabbit-workflow-<ref> with '/' translated to '-')
SRC=$(find "$TMP" -maxdepth 1 -type d -name "rabbit-workflow-*" | head -1)
if [ -z "$SRC" ] || [ ! -d "$SRC" ]; then
  echo "error: could not locate extracted source dir under $TMP" >&2
  exit 1
fi

# Run the Python installer
python3 "$SRC/install.py" --src "$SRC" --target "$(pwd)/.rabbit"

echo ""
echo "Installed. Next steps:"
echo "  cd .rabbit/ && claude"
echo ""
echo "Then commit the install into your project's git:"
echo "  git add .rabbit/ && git commit -m 'install rabbit'"
