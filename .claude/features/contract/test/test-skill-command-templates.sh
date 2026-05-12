#!/bin/bash
# test-skill-command-templates.sh — verify skill-template.md and command-template.md
# exist, carry valid frontmatter, and contain required blockquote identity lines.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATES_DIR="$FEATURE_DIR/templates"
SKILL_TMPL="$TEMPLATES_DIR/skill-template.md"
CMD_TMPL="$TEMPLATES_DIR/command-template.md"
FAIL=0

fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}

# Helper: extract YAML frontmatter (content between first pair of --- lines)
frontmatter() {
  local file="$1"
  awk '/^---$/{found++; if(found==2) exit; next} found==1{print}' "$file"
}

# Helper: body after frontmatter (after second ---)
body_after_frontmatter() {
  local file="$1"
  awk '/^---$/{found++} found>=2{print}' "$file" | tail -n +2
}

# ── Test 1: skill-template.md exists ─────────────────────────────────────────
if [ ! -f "$SKILL_TMPL" ]; then
  fail "skill-template.md does not exist: $SKILL_TMPL"
else
  echo "ok: skill-template.md exists"
fi

# ── Test 2: command-template.md exists ───────────────────────────────────────
if [ ! -f "$CMD_TMPL" ]; then
  fail "command-template.md does not exist: $CMD_TMPL"
else
  echo "ok: command-template.md exists"
fi

# For the remaining tests, only proceed per-file if the file exists.

# ── Test 3: skill-template.md frontmatter has template_version: ──────────────
if [ -f "$SKILL_TMPL" ]; then
  if ! frontmatter "$SKILL_TMPL" | grep -qE '^template_version:'; then
    fail "skill-template.md frontmatter missing 'template_version:' field"
  else
    echo "ok: skill-template.md frontmatter has template_version:"
  fi
else
  fail "skill-template.md missing — cannot check frontmatter (test 3)"
fi

# ── Test 4: command-template.md frontmatter has template_version: ────────────
if [ -f "$CMD_TMPL" ]; then
  if ! frontmatter "$CMD_TMPL" | grep -qE '^template_version:'; then
    fail "command-template.md frontmatter missing 'template_version:' field"
  else
    echo "ok: command-template.md frontmatter has template_version:"
  fi
else
  fail "command-template.md missing — cannot check frontmatter (test 4)"
fi

# ── Test 5: skill-template.md body has blockquote starting with
#            "> **rabbit-workflow skill" ─────────────────────────────────────
if [ -f "$SKILL_TMPL" ]; then
  if ! body_after_frontmatter "$SKILL_TMPL" | grep -qE '^> \*\*rabbit-workflow skill'; then
    fail "skill-template.md body missing blockquote line starting with '> **rabbit-workflow skill'"
  else
    echo "ok: skill-template.md body has '> **rabbit-workflow skill' blockquote"
  fi
else
  fail "skill-template.md missing — cannot check body blockquote (test 5)"
fi

# ── Test 6: command-template.md body has blockquote starting with
#            "> **rabbit-workflow command" ────────────────────────────────────
if [ -f "$CMD_TMPL" ]; then
  if ! body_after_frontmatter "$CMD_TMPL" | grep -qE '^> \*\*rabbit-workflow command'; then
    fail "command-template.md body missing blockquote line starting with '> **rabbit-workflow command'"
  else
    echo "ok: command-template.md body has '> **rabbit-workflow command' blockquote"
  fi
else
  fail "command-template.md missing — cannot check body blockquote (test 6)"
fi

# Required frontmatter fields for both templates
REQUIRED_FIELDS="name description version owner deprecation_criterion"

# ── Test 7: skill-template.md frontmatter has all required fields ─────────────
if [ -f "$SKILL_TMPL" ]; then
  fm="$(frontmatter "$SKILL_TMPL")"
  for field in $REQUIRED_FIELDS; do
    if ! echo "$fm" | grep -qE "^${field}:"; then
      fail "skill-template.md frontmatter missing required field: $field"
    else
      echo "ok: skill-template.md frontmatter has field: $field"
    fi
  done
else
  fail "skill-template.md missing — cannot check required frontmatter fields (test 7)"
fi

# ── Test 8: command-template.md frontmatter has all required fields ───────────
if [ -f "$CMD_TMPL" ]; then
  fm="$(frontmatter "$CMD_TMPL")"
  for field in $REQUIRED_FIELDS; do
    if ! echo "$fm" | grep -qE "^${field}:"; then
      fail "command-template.md frontmatter missing required field: $field"
    else
      echo "ok: command-template.md frontmatter has field: $field"
    fi
  done
else
  fail "command-template.md missing — cannot check required frontmatter fields (test 8)"
fi

if [ $FAIL -ne 0 ]; then
  echo "test-skill-command-templates: FAIL" >&2
  exit 1
fi

echo "test-skill-command-templates: all checks passed."
