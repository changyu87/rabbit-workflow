#!/usr/bin/env python3
# test-skill-command-templates.py — verify skill-template.md and command-template.md
# exist, carry valid frontmatter, and contain required blockquote identity lines.

import os
import sys
import re

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TEMPLATES_DIR = os.path.join(FEATURE_DIR, "templates")
SKILL_TMPL = os.path.join(TEMPLATES_DIR, "skill-template.md")
CMD_TMPL = os.path.join(TEMPLATES_DIR, "command-template.md")
FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def get_frontmatter(filepath):
    """Extract YAML frontmatter (content between first pair of --- lines)."""
    with open(filepath) as f:
        lines = f.readlines()
    in_fm = False
    fm_lines = []
    count = 0
    for line in lines:
        if line.strip() == "---":
            count += 1
            if count == 1:
                in_fm = True
            elif count == 2:
                break
            continue
        if in_fm:
            fm_lines.append(line)
    return "".join(fm_lines)


def get_body_after_frontmatter(filepath):
    """Body after frontmatter (after second ---)."""
    with open(filepath) as f:
        lines = f.readlines()
    count = 0
    body_lines = []
    past_fm = False
    for line in lines:
        if line.strip() == "---":
            count += 1
            if count == 2:
                past_fm = True
            continue
        if past_fm:
            body_lines.append(line)
    return "".join(body_lines)


# ── Test 1: skill-template.md exists ─────────────────────────────────────────
if not os.path.isfile(SKILL_TMPL):
    fail(f"skill-template.md does not exist: {SKILL_TMPL}")
else:
    print("ok: skill-template.md exists")

# ── Test 2: command-template.md exists ───────────────────────────────────────
if not os.path.isfile(CMD_TMPL):
    fail(f"command-template.md does not exist: {CMD_TMPL}")
else:
    print("ok: command-template.md exists")

# ── Test 3: skill-template.md frontmatter has template_version: ──────────────
if os.path.isfile(SKILL_TMPL):
    fm = get_frontmatter(SKILL_TMPL)
    if not re.search(r'^template_version:', fm, re.MULTILINE):
        fail("skill-template.md frontmatter missing 'template_version:' field")
    else:
        print("ok: skill-template.md frontmatter has template_version:")
else:
    fail("skill-template.md missing — cannot check frontmatter (test 3)")

# ── Test 4: command-template.md frontmatter has template_version: ────────────
if os.path.isfile(CMD_TMPL):
    fm = get_frontmatter(CMD_TMPL)
    if not re.search(r'^template_version:', fm, re.MULTILINE):
        fail("command-template.md frontmatter missing 'template_version:' field")
    else:
        print("ok: command-template.md frontmatter has template_version:")
else:
    fail("command-template.md missing — cannot check frontmatter (test 4)")

# ── Test 5: skill-template.md body has blockquote starting with
#            "> **rabbit-workflow skill" ─────────────────────────────────────
if os.path.isfile(SKILL_TMPL):
    body = get_body_after_frontmatter(SKILL_TMPL)
    if not re.search(r'^> \*\*rabbit-workflow skill', body, re.MULTILINE):
        fail("skill-template.md body missing blockquote line starting with '> **rabbit-workflow skill'")
    else:
        print("ok: skill-template.md body has '> **rabbit-workflow skill' blockquote")
else:
    fail("skill-template.md missing — cannot check body blockquote (test 5)")

# ── Test 6: command-template.md body has blockquote starting with
#            "> **rabbit-workflow command" ────────────────────────────────────
if os.path.isfile(CMD_TMPL):
    body = get_body_after_frontmatter(CMD_TMPL)
    if not re.search(r'^> \*\*rabbit-workflow command', body, re.MULTILINE):
        fail("command-template.md body missing blockquote line starting with '> **rabbit-workflow command'")
    else:
        print("ok: command-template.md body has '> **rabbit-workflow command' blockquote")
else:
    fail("command-template.md missing — cannot check body blockquote (test 6)")

REQUIRED_FIELDS = ["name", "description", "version", "owner", "deprecation_criterion"]

# ── Test 7: skill-template.md frontmatter has all required fields ─────────────
if os.path.isfile(SKILL_TMPL):
    fm = get_frontmatter(SKILL_TMPL)
    for field in REQUIRED_FIELDS:
        if not re.search(rf'^{re.escape(field)}:', fm, re.MULTILINE):
            fail(f"skill-template.md frontmatter missing required field: {field}")
        else:
            print(f"ok: skill-template.md frontmatter has field: {field}")
else:
    fail("skill-template.md missing — cannot check required frontmatter fields (test 7)")

# ── Test 8: command-template.md frontmatter has all required fields ───────────
if os.path.isfile(CMD_TMPL):
    fm = get_frontmatter(CMD_TMPL)
    for field in REQUIRED_FIELDS:
        if not re.search(rf'^{re.escape(field)}:', fm, re.MULTILINE):
            fail(f"command-template.md frontmatter missing required field: {field}")
        else:
            print(f"ok: command-template.md frontmatter has field: {field}")
else:
    fail("command-template.md missing — cannot check required frontmatter fields (test 8)")

if FAIL != 0:
    print("test-skill-command-templates: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-skill-command-templates: all checks passed.")
