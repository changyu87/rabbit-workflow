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
# Channel selection (spec Inv 26):
#   With no RABBIT_REF override, install.sh resolves the LATEST published
#   GitHub release dynamically (the releases/latest tag_name) — the same
#   release source install.py --update and the update-check use. First-install
#   therefore tracks latest with no per-release bump (Fixes #848).
#
#   The named development channel is main-centric: 'main' is the default
#   development tip and 'dev' coexists as the legacy opt-in channel during the
#   transition window. Either branch ref can be pinned explicitly below.
#
#   Pin a specific version (explicit override short-circuits the lookup):
#     RABBIT_REF=v9.0.26    curl -sSL .../install.sh | bash
#     RABBIT_REF=release/1.0 curl -sSL .../install.sh | bash
#
#   Default development tip (main-centric):
#     RABBIT_REF=main curl -sSL .../install.sh | bash
#
#   Legacy bleeding-edge channel (developers — opt-in coexistence):
#     RABBIT_REF=dev curl -sSL .../install.sh | bash
#
# Env vars:
#   RABBIT_REPO  — default changyu87/rabbit-workflow
#   RABBIT_REF   — explicit ref override (branch, tag, or SHA); when unset the
#                  latest published release is resolved dynamically.

set -euo pipefail

RABBIT_REPO="${RABBIT_REPO:-changyu87/rabbit-workflow}"

# Offline fallback: a last-known-good release tag used ONLY when the dynamic
# latest-release lookup fails (network/offline, rate-limit, API outage). This
# is a safety net, NOT the primary channel — the default path resolves latest
# dynamically. MUST byte-equal install.py's HARDCODED_STABLE_DEFAULT (Inv 26/27
# lock-step) and MUST NOT be 'dev'.
RABBIT_FALLBACK_REF="v9.0.26"

# Resolve the latest published release's tag_name via the GitHub Releases API.
# Echoes the tag on success; empty on any failure (caller falls back).
resolve_latest_release() {
  local body tag
  body=$(curl -fsSL \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${RABBIT_REPO}/releases/latest" 2>/dev/null) || return 0
  # Extract "tag_name": "<tag>" without requiring jq.
  tag=$(printf '%s' "$body" \
    | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -1 \
    | sed -E 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')
  printf '%s' "$tag"
}

# Ref selection: explicit RABBIT_REF wins; otherwise resolve latest dynamically;
# otherwise fall back to the hardcoded last-known-good tag (never 'dev').
if [ -n "${RABBIT_REF:-}" ]; then
  : # explicit override honored verbatim
else
  RABBIT_REF=$(resolve_latest_release)
  if [ -z "${RABBIT_REF}" ]; then
    RABBIT_REF="${RABBIT_FALLBACK_REF}"
    echo "warning: could not resolve latest release; falling back to ${RABBIT_FALLBACK_REF}" >&2
  fi
fi

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
