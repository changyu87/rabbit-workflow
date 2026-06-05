#!/usr/bin/env python3
"""test-skill-structure.py — E2E for the rabbit-housekeep skill structure.

Asserts, against the real feature tree:

  t0: skills/rabbit-housekeep/SKILL.md exists and is non-empty.
  t1: SKILL.md frontmatter declares name: rabbit-housekeep, a version, an
      owner, and a deprecation_criterion.
  t2: feature.json manifest publishes the skill (publish_skill sourcing
      skills/rabbit-housekeep/SKILL.md), so the skill is deployable.
  t3: SKILL.md embeds coding-rules.md §6 ("Cleanup: Prove It Dead or Flag
      It") VERBATIM — the §6 text extracted from the canonical policy file
      appears byte-for-byte inside the SKILL.md body. This is the Verbatim
      Policy Embedding guarantee (no paraphrase).
  t4: SKILL.md documents the subagent-dispatching no-Agent()-nesting
      constraint: it names the two-level-nesting prohibition and states the
      skill MUST NOT be invoked inside an Agent() call.
  t5: SKILL.md embeds spec-rules.md §4 "Script-Backed Orchestration" bullet
      VERBATIM — the bullet text extracted from the canonical policy file
      appears byte-for-byte inside the SKILL.md body (Verbatim Policy
      Embedding, no paraphrase).
  t6: SKILL.md documents the script-backed-orchestration verify-or-flag
      dimension: it invokes scripts/check-script-backed.py and routes each
      non-conformant step through the prove-it-dead-or-flag disposition.

Non-interactive. Exits non-zero on failure.

Version: 0.3.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
SKILL_MD = os.path.join(
    FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md"
)
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
CODING_RULES = os.path.join(
    REPO_ROOT, ".claude", "features", "policy", "coding-rules.md"
)
SPEC_RULES = os.path.join(
    REPO_ROOT, ".claude", "features", "policy", "spec-rules.md"
)

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t0
if not (os.path.isfile(SKILL_MD) and os.path.getsize(SKILL_MD) > 0):
    fail("t0", f"missing or empty: {SKILL_MD}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "SKILL.md exists and is non-empty")

with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

# t1: frontmatter
fm = re.match(r"^---\n(.*?)\n---\n", skill_text, re.DOTALL)
if not fm:
    fail("t1", "no YAML frontmatter at top of SKILL.md")
else:
    fmt = fm.group(1)
    needed = {
        "name": re.search(r"^name:\s*rabbit-housekeep\s*$", fmt, re.MULTILINE),
        "version": re.search(r"^version:\s*\d+\.\d+\.\d+\s*$", fmt, re.MULTILINE),
        "owner": re.search(r"^owner:\s*.+$", fmt, re.MULTILINE),
        "deprecation_criterion": re.search(
            r"^deprecation_criterion:\s*.+$", fmt, re.MULTILINE),
    }
    missing = [k for k, v in needed.items() if not v]
    if missing:
        fail("t1", f"frontmatter missing/invalid: {missing}")
    else:
        ok("t1", "frontmatter declares name/version/owner/deprecation_criterion")

# t2: manifest publishes the skill
with open(FEATURE_JSON, encoding="utf-8") as f:
    fjson = json.load(f)
manifest = fjson.get("manifest", [])
published = any(
    m.get("api") == "publish_skill"
    and m.get("args", {}).get("source") == "skills/rabbit-housekeep/SKILL.md"
    for m in manifest
)
if published:
    ok("t2", "manifest publishes the rabbit-housekeep skill")
else:
    fail("t2", f"no publish_skill entry sourcing the SKILL.md; manifest={manifest}")

# t3: verbatim coding-rules §6 embed
with open(CODING_RULES, encoding="utf-8") as f:
    rules_text = f.read()
sec_match = re.search(
    r"(## 6\. Cleanup: Prove It Dead or Flag It\n.*?)(?=\n## \d)",
    rules_text,
    re.DOTALL,
)
if not sec_match:
    fail("t3", "could not locate §6 in coding-rules.md (extraction failed)")
else:
    # Strip a trailing horizontal-rule separator ('---') and surrounding
    # blank lines: the rule body is §6's prose, not the doc delimiter.
    section = sec_match.group(1).rstrip()
    section = re.sub(r"\n+-{3,}\s*$", "", section).rstrip()
    if section in skill_text:
        ok("t3", "coding-rules §6 is embedded verbatim (byte-for-byte)")
    else:
        fail("t3", "SKILL.md does not contain coding-rules §6 verbatim; "
                   "the embedded block must match the policy source exactly")

# t4: subagent-dispatching no-Agent-nesting constraint documented
nesting = re.search(
    r"(?:two-level|2-level)(?:\s+\w+){0,2}\s+nesting",
    skill_text,
    re.IGNORECASE,
)
no_agent = re.search(
    r"(?:MUST\s+NOT|must not).{0,80}Agent\(", skill_text, re.IGNORECASE | re.DOTALL
)
dispatching = re.search(r"subagent-dispatching", skill_text, re.IGNORECASE)
if nesting and no_agent and dispatching:
    ok("t4", "subagent-dispatching no-Agent()-nesting constraint documented")
else:
    fail("t4", "SKILL.md must name itself subagent-dispatching, state it MUST "
               "NOT be invoked inside an Agent() call, and name the two-level "
               f"nesting constraint (nesting={bool(nesting)}, "
               f"no_agent={bool(no_agent)}, dispatching={bool(dispatching)})")

# t5: verbatim spec-rules §4 Script-Backed Orchestration embed
with open(SPEC_RULES, encoding="utf-8") as f:
    spec_rules_text = f.read()
sb_match = re.search(
    r"(- \*\*Script-Backed Orchestration\*\*.*?)(?=\n\n- \*\*)",
    spec_rules_text,
    re.DOTALL,
)
if not sb_match:
    fail("t5", "could not locate §4 Script-Backed Orchestration bullet in "
               "spec-rules.md (extraction failed)")
else:
    sb_bullet = sb_match.group(1).rstrip()
    if sb_bullet in skill_text:
        ok("t5", "spec-rules §4 Script-Backed Orchestration embedded verbatim")
    else:
        fail("t5", "SKILL.md does not contain spec-rules §4 Script-Backed "
                   "Orchestration verbatim; the embedded block must match the "
                   "policy source exactly")

# t6: script-backed-orchestration verify-or-flag dimension documented
invokes_script = re.search(
    r"check-script-backed\.py", skill_text
)
flag_disposition = re.search(
    r"(?:FLAG|flag).{0,120}housekeeping.{0,40}sub-issue",
    skill_text,
    re.IGNORECASE | re.DOTALL,
)
if invokes_script and flag_disposition:
    ok("t6", "script-backed-orchestration dimension documented (invokes "
             "check-script-backed.py + flag disposition)")
else:
    fail("t6", "SKILL.md must invoke scripts/check-script-backed.py and route "
               "non-conformant steps through the flag disposition "
               f"(invokes={bool(invokes_script)}, "
               f"flag={bool(flag_disposition)})")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
