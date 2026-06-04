#!/usr/bin/env python3
"""test-retirement-skill-injection.py — e2e regression for issue #391.

Asserts that the Skill-path prompt injection surface (retired Inv 55 /
retired Inv 56, shrunk Inv 47) is fully absent:

  t1: hooks/prompt-injector.py source is absent from contract feature.
  t2: deployed .claude/hooks/prompt-injector.py is absent.
  t3: .claude/settings.json carries no PreToolUse entry whose command
      string references prompt-injector.py (other PreToolUse entries —
      notably scope-guard.py — remain unaffected).
  t4: contract feature.json has empty manifest and empty runtime.
  t5: every kind=='skill' prompts entry is absent from every feature.json
      under .claude/features/ (only kind=='subagent' entries remain).
  t6: every retired skill-passthrough template file is absent from
      .claude/features/contract/templates/prompts/.

Each assertion fails closed: presence of any retired artifact exits 1.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when an automated cross-feature dead-artifact
linter spanning the whole repo is wired into the Stop hook.
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")

RETIRED_SKILL_PASSTHROUGHS = [
    "rabbit-feature-touch.txt",
    "rabbit-spec-update.txt",
    "rabbit-feature-scaffold.txt",
    "rabbit-feature-audit.txt",
    "rabbit-feature-scope.txt",
    "rabbit-config.txt",
    "rabbit-issue.txt",
    "rabbit-decompose.txt",
    "rabbit-auto-evolve.txt",
]

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS t{n}: {msg}")
    PASS += 1


def ko(n, msg):
    global FAIL
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    FAIL += 1


# t1 — source hook absent
src_hook = os.path.join(FEATURE_DIR, "hooks", "prompt-injector.py")
if os.path.exists(src_hook):
    ko("1", f"source hook still present at {src_hook}")
else:
    ok("1", "hooks/prompt-injector.py source is absent")

# t2 — deployed hook absent
deployed_hook = os.path.join(REPO_ROOT, ".claude", "hooks", "prompt-injector.py")
if os.path.exists(deployed_hook):
    ko("2", f"deployed hook still present at {deployed_hook}")
else:
    ok("2", ".claude/hooks/prompt-injector.py deployed copy is absent")

# t3 — settings.json carries no prompt-injector.py entry
settings_path = os.path.join(REPO_ROOT, ".claude", "settings.json")
with open(settings_path) as f:
    settings = json.load(f)
pre_tool_use = settings.get("hooks", {}).get("PreToolUse", []) or []
offending = []
for group in pre_tool_use:
    for h in group.get("hooks", []) or []:
        cmd = h.get("command", "") or ""
        if "prompt-injector.py" in cmd:
            offending.append(cmd)
if offending:
    ko("3", f"settings.json PreToolUse still registers prompt-injector.py: {offending}")
else:
    ok("3", "settings.json PreToolUse has no prompt-injector.py command")

# t4 — contract feature.json has empty manifest and runtime
contract_fjson = os.path.join(FEATURE_DIR, "feature.json")
with open(contract_fjson) as f:
    fdata = json.load(f)
manifest = fdata.get("manifest")
runtime = fdata.get("runtime")
if manifest == []:
    ok("4a", "contract feature.json manifest is []")
else:
    ko("4a", f"contract feature.json manifest must be [], got {manifest!r}")
if runtime == {}:
    ok("4b", "contract feature.json runtime is {}")
else:
    ko("4b", f"contract feature.json runtime must be {{}}, got {runtime!r}")

# t5 — no kind:skill prompts entries remain anywhere
skill_entries = []
for fname in sorted(os.listdir(FEATURES_ROOT)):
    fjson_path = os.path.join(FEATURES_ROOT, fname, "feature.json")
    if not os.path.isfile(fjson_path):
        continue
    try:
        data = json.load(open(fjson_path))
    except (OSError, json.JSONDecodeError):
        continue
    for entry in data.get("prompts", []) or []:
        if entry.get("kind") == "skill":
            skill_entries.append((fname, entry.get("id")))
if skill_entries:
    ko("5", f"kind:skill prompts entries still present: {skill_entries}")
else:
    ok("5", "no kind:skill prompts entries remain in any feature.json")

# t6 — each retired skill-passthrough template absent from disk
prompts_dir = os.path.join(FEATURE_DIR, "templates", "prompts")
for tname in RETIRED_SKILL_PASSTHROUGHS:
    p = os.path.join(prompts_dir, tname)
    if os.path.exists(p):
        ko(f"6[{tname}]", f"retired template still present at {p}")
    else:
        ok(f"6[{tname}]", f"templates/prompts/{tname} is absent")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
