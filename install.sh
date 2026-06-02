#!/usr/bin/env bash
# install.sh — install rabbit into the current project as .rabbit/
#
# install.sh is for FIRST-TIME installs only. To update an existing install,
# run `python3 .rabbit/install.py --update` directly (Inv 22a, Fixes #273).
#
# One-liner usage (installs the latest stable release):
#   curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/dev/install.sh | bash
#
# Or download + run:
#   curl -fsSLO https://raw.githubusercontent.com/changyu87/rabbit-workflow/dev/install.sh && bash install.sh
#
# Channel selection (spec Inv 24):
#   The default RABBIT_REF tracks the latest stable release branch. Cutting
#   a new release (e.g. release/1.1) bumps this default in the same PR.
#
#   Pin a specific version:
#     RABBIT_REF=release/1.0 curl -sSL .../install.sh | bash
#     RABBIT_REF=v1.0.0      curl -sSL .../install.sh | bash
#
#   Bleeding edge (developers — opt-in only):
#     RABBIT_REF=dev curl -sSL .../install.sh | bash
#
# Env vars:
#   RABBIT_REPO  — default changyu87/rabbit-workflow
#   RABBIT_REF   — default release/1.11.0 (branch, tag, or SHA)

set -euo pipefail

RABBIT_REPO="${RABBIT_REPO:-changyu87/rabbit-workflow}"
RABBIT_REF="${RABBIT_REF:-release/1.11.0}"

# Pre-flight
for cmd in python3 curl tar; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: $cmd is required but not found in PATH" >&2; exit 1; }
done

# Refuse unconditionally when .rabbit/ already exists (Inv 22a). install.sh
# is for first-time installs only — updates go through install.py directly.
if [ -d .rabbit ]; then
  echo "error: .rabbit/ already exists in $(pwd); to update an existing install, run:" >&2
  echo "         python3 .rabbit/install.py --update" >&2
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

# Export the version pin label install.py will write into <target>/.version.
# Default to $RABBIT_REF (the fetched ref) so one-liner installs record the
# branch/tag/SHA they actually pulled. An externally-set RABBIT_INSTALLED_REF
# (e.g. from test stubs or explicit override) wins. (rabbit-cage spec Inv 22e,
# Fixes #258)
export RABBIT_INSTALLED_REF="${RABBIT_INSTALLED_REF:-$RABBIT_REF}"

# Run the Python installer
python3 "$SRC/install.py" --src "$SRC" --target "$(pwd)/.rabbit"

echo ""
echo "Installed. Next steps:"
echo "  cd .rabbit/ && claude"
echo ""
echo "Then commit the install into your project's git:"
echo "  git add .rabbit/ && git commit -m 'install rabbit'"
