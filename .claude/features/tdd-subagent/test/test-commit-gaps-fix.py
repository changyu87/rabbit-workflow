#!/usr/bin/env python3
# E2E test for tdd-subagent spec invariants 12 and 13 (post-BACKLOG-12
# renumber; were Inv 16 and 17 in v1.19.0):
#
#   Inv 12. After rabbit-spec returns in Step 3, the rabbit-feature-touch
#       dispatcher MUST commit any modifications to docs/spec/spec.md BEFORE
#       proceeding to Step 5. Commit message pattern:
#       "spec(<feature>): update spec for ...". Skipped if rabbit-spec made
#       no changes.
#
#   Inv 13. In Step 9 (UNLOCK) of the per-feature TDD subagent prompt
#       assembled by dispatch-tdd-subagent.py, the subagent MUST commit
#       feature.json BEFORE emitting the HANDOFF block. Commit message
#       pattern: "chore(<feature>): advance tdd_state to test-green".
#
# Inv 12 is asserted against the deployed SKILL.md (the surface artifact
# downstream consumers see). Inv 13 is asserted against the prompt produced by
# dispatch-tdd-subagent.py for a real feature.

import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

SOURCE_SKILL = os.path.join(
    REPO_ROOT,
    '.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md',
)
DEPLOYED_SKILL = os.path.join(
    REPO_ROOT, '.claude/skills/rabbit-feature-touch/SKILL.md'
)
DISPATCH_PY = os.path.join(
    REPO_ROOT,
    '.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py',
)
SPEC_PATH = os.path.join(
    REPO_ROOT, '.claude/features/tdd-subagent/docs/spec/spec.md'
)

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def load_skill():
    if not os.path.isfile(SOURCE_SKILL):
        ko(f"source SKILL.md missing: {SOURCE_SKILL}")
        sys.exit(1)
    if not os.path.isfile(DEPLOYED_SKILL):
        ko(f"deployed SKILL.md missing: {DEPLOYED_SKILL}")
        sys.exit(1)
    with open(SOURCE_SKILL) as f:
        src = f.read()
    with open(DEPLOYED_SKILL) as f:
        dep = f.read()
    if src != dep:
        ko("deployed SKILL.md differs from source")
        sys.exit(1)
    return dep


def _step_section(skill_text, n):
    pattern = rf"###\s+Step\s+{n}\s+[-—].*?(?=\n###\s+|\Z)"
    m = re.search(pattern, skill_text, re.DOTALL)
    return m.group(0) if m else ""


# ---- Invariant 16: Step 3 commits spec.md after rabbit-spec returns ----------

def t_inv16_step3_commits_spec_md():
    skill = load_skill()
    body = _step_section(skill, 3)
    if not body:
        ko("inv16: Step 3 section not found in SKILL.md")
        return
    # The Step 3 body must mention adding/committing spec.md
    if not re.search(r"git\s+add\b.*spec\.md", body, re.DOTALL):
        ko("inv16: Step 3 does not show 'git add ... spec.md'")
    else:
        ok("inv16: Step 3 stages spec.md after rabbit-spec returns")

    if not re.search(r"git\s+commit\b", body):
        ko("inv16: Step 3 does not run 'git commit'")
    else:
        ok("inv16: Step 3 runs git commit")

    # Commit message pattern: spec(<feature>): update spec for ...
    if not re.search(r"spec\([^)]+\):\s*update\s+spec\s+for\b", body, re.IGNORECASE):
        ko("inv16: Step 3 commit message does not match 'spec(<feature>): update spec for ...'")
    else:
        ok("inv16: Step 3 commit message matches required pattern")


def t_inv16_step3_skip_when_no_changes():
    skill = load_skill()
    body = _step_section(skill, 3)
    if not body:
        ko("inv16: Step 3 section not found in SKILL.md")
        return
    # Spec mandates: skipped if rabbit-spec made no changes.
    if re.search(r"skip|no\s+changes|nothing\s+to\s+commit|if\s+.*diff", body, re.IGNORECASE):
        ok("inv16: Step 3 documents skip-when-no-changes behaviour")
    else:
        ko("inv16: Step 3 does not document skip-when-no-changes behaviour")


def t_inv16_step3_commits_before_step5():
    skill = load_skill()
    # The commit instruction must appear before the Step 5 heading.
    m_step5 = re.search(r"###\s+Step\s+5\s+[-—]", skill)
    if not m_step5:
        ko("inv16: Step 5 heading not found")
        return
    step5_start = m_step5.start()
    # Find a 'spec(...): update spec for' commit instruction in Step 3 section
    body = _step_section(skill, 3)
    m_commit = re.search(r"spec\([^)]+\):\s*update\s+spec\s+for\b", body, re.IGNORECASE)
    if not m_commit:
        ko("inv16: commit instruction not present in Step 3")
        return
    # Confirm the body of Step 3 ends before Step 5
    step3_match = re.search(
        r"###\s+Step\s+3\s+[-—].*?(?=\n###\s+|\Z)", skill, re.DOTALL
    )
    if step3_match and step3_match.end() <= step5_start:
        ok("inv16: Step 3 commit instruction appears before Step 5")
    else:
        ko("inv16: Step 3 section does not end before Step 5")


# ---- Invariant 17: dispatch-tdd-subagent.py UNLOCK commits feature.json ------

def _run_dispatch(extra_args=None):
    args = [
        sys.executable, DISPATCH_PY,
        '--scope', 'tdd-subagent',
        '--spec', SPEC_PATH,
        '--human-approval-gate', 'false',
    ]
    if extra_args:
        args.extend(extra_args)
    res = subprocess.run(args, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        ko(f"dispatch-tdd-subagent.py returned {res.returncode}: {res.stderr}")
        return ""
    return res.stdout


def _unlock_section(prompt):
    # Step 9 — UNLOCK section extends until the next "═══" block heading
    # (HANDOFF) or end of text.
    m = re.search(
        r"STEP\s+9\s+[-—]\s+UNLOCK\s*\n[═=]+\s*\n(.*?)(?=\n[═=]{5,}\s*\n|\Z)",
        prompt, re.DOTALL,
    )
    return m.group(1) if m else ""


def t_inv17_unlock_commits_feature_json():
    prompt = _run_dispatch()
    if not prompt:
        return
    unlock = _unlock_section(prompt)
    if not unlock:
        ko("inv17: STEP 9 — UNLOCK section not found in dispatch prompt")
        return
    if not re.search(r"git\s+add\b.*feature\.json", unlock, re.DOTALL):
        ko("inv17: UNLOCK does not show 'git add ... feature.json'")
    else:
        ok("inv17: UNLOCK stages feature.json")

    if not re.search(r"git\s+commit\b", unlock):
        ko("inv17: UNLOCK does not run 'git commit'")
    else:
        ok("inv17: UNLOCK runs git commit")

    # Commit message pattern: chore(<feature>): advance tdd_state to test-green
    if not re.search(
        r"chore\([^)]+\):\s*advance\s+tdd_state\s+to\s+test-green",
        unlock, re.IGNORECASE,
    ):
        ko("inv17: UNLOCK commit message does not match 'chore(<feature>): advance tdd_state to test-green'")
    else:
        ok("inv17: UNLOCK commit message matches required pattern")


def t_inv17_unlock_commits_before_handoff():
    prompt = _run_dispatch()
    if not prompt:
        return
    # Locate the UNLOCK section start, HANDOFF block, and the commit
    # instruction inside the UNLOCK body (not the spec embed earlier in
    # the prompt).
    m_unlock_hdr = re.search(r"STEP\s+9\s+[-—]\s+UNLOCK\s*\n[═=]+\s*\n", prompt)
    m_handoff = re.search(r"HANDOFF\s*\(emit on completion\)", prompt)
    if not m_unlock_hdr:
        ko("inv17: STEP 9 — UNLOCK header not found in prompt")
        return
    if not m_handoff:
        ko("inv17: HANDOFF block not found in prompt")
        return
    unlock_body = prompt[m_unlock_hdr.end():m_handoff.start()]
    m_commit = re.search(
        r"chore\([^)]+\):\s*advance\s+tdd_state\s+to\s+test-green",
        unlock_body, re.IGNORECASE,
    )
    if not m_commit:
        ko("inv17: feature.json commit instruction not found inside UNLOCK section (before HANDOFF)")
        return
    ok("inv17: UNLOCK commit instruction appears between UNLOCK header and HANDOFF block")


def t_inv17_substitutes_feature_name_in_commit_msg():
    # When --scope X is passed, the commit message must use X (not literal {feature_name}).
    prompt = _run_dispatch()
    if not prompt:
        return
    if "chore(tdd-subagent): advance tdd_state to test-green" in prompt:
        ok("inv17: commit message substitutes feature name from --scope")
    else:
        ko("inv17: commit message does not substitute feature name from --scope")


# ---- Run -------------------------------------------------------------------

print("running tdd-subagent commit-gaps-fix tests (inv 16, 17)")
t_inv16_step3_commits_spec_md()
t_inv16_step3_skip_when_no_changes()
t_inv16_step3_commits_before_step5()
t_inv17_unlock_commits_feature_json()
t_inv17_unlock_commits_before_handoff()
t_inv17_substitutes_feature_name_in_commit_msg()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
