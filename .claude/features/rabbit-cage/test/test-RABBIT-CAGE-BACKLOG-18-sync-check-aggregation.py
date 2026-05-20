#!/usr/bin/env python3
"""BACKLOG-18 FULL E2E test for sync-check.py aggregation (Inv 37, 38, 76).

Builds a realistic temp repo (real CLAUDE.md, real @-import files, real git
history), sets up multiple simultaneous pending conditions by writing actual
marker files, invokes sync-check.py as a subprocess, and asserts:

  - Exactly one JSON object is emitted.
  - systemMessage contains one [rabbit] line per pending condition,
    ordered by Inv 37 priority.
  - Consume-on-read markers are consumed exactly once.
  - A second invocation does not leak any condition.
  - The zero-condition case emits no JSON.
"""
import json
import os
import shutil
import subprocess
import sys

from test_helpers import REPO_ROOT, make_git_repo, run_sync

SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def count_json_objects(data):
    data = data.strip()
    if not data:
        return 0
    decoder = json.JSONDecoder()
    idx = 0
    count = 0
    while idx < len(data):
        rest = data[idx:].lstrip()
        if not rest:
            break
        try:
            _, end = decoder.raw_decode(rest)
            count += 1
            consumed = (len(data) - len(data[idx:])) + end
            idx = consumed
        except Exception:
            break
    return count


def parse_one(data):
    return json.loads(data.strip())


print("test-RABBIT-CAGE-BACKLOG-18-sync-check-aggregation.py")
print("FULL E2E: sync-check.py aggregation across multiple pending conditions")
print()

tmproots = []
try:
    # ---- E2E SCENARIO 1: scope-guard-off + human-approval + skills-updated ----
    print("=== t1: three simultaneous conditions aggregate into one JSON ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)

    with open(os.path.join(tmproot, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    with open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    with open(os.path.join(tmproot, ".rabbit-skills-updated"), "w") as f:
        f.write("rabbit-config\nrabbit-feature-spec\n")

    out = run_sync(tmproot)
    n = count_json_objects(out)
    if n == 1:
        ok("exactly one JSON object emitted")
    else:
        fail_t(f"expected 1 JSON object, got {n}; raw: {out!r}")

    try:
        obj = parse_one(out)
        ok("emitted output parses as JSON")
    except Exception as e:
        fail_t(f"emitted output does NOT parse as JSON: {e}; raw: {out!r}")
        obj = {}

    msg = obj.get("systemMessage", "")
    has_scope = "SCOPE GUARD OFF" in msg
    has_ha = "HUMAN APPROVAL BYPASS" in msg
    has_skills = "Skills updated" in msg

    if has_scope and has_ha and has_skills:
        ok("all three [rabbit] lines present in aggregated systemMessage")
    else:
        fail_t(
            f"missing line(s) — scope={has_scope}, human-approval={has_ha}, "
            f"skills={has_skills}; msg={msg!r}"
        )

    idx_scope = msg.find("SCOPE GUARD OFF")
    idx_ha = msg.find("HUMAN APPROVAL BYPASS")
    idx_sk = msg.find("Skills updated")
    if 0 <= idx_scope < idx_ha < idx_sk:
        ok("lines ordered per Inv 37 priority: scope(3) < human-approval(4) < skills(5)")
    else:
        fail_t(f"line ordering wrong: scope={idx_scope} ha={idx_ha} sk={idx_sk}")

    # consume-on-read markers
    skills_marker = os.path.join(tmproot, ".rabbit-skills-updated")
    if not os.path.exists(skills_marker):
        ok(".rabbit-skills-updated consumed on emit")
    else:
        fail_t(".rabbit-skills-updated NOT consumed — should be deleted")

    # session override should NOT be consumed
    override = os.path.join(tmproot, ".rabbit-scope-override")
    if os.path.exists(override):
        ok(".rabbit-scope-override (session) preserved (not consumed)")
    else:
        fail_t(".rabbit-scope-override removed unexpectedly")

    # human-approval marker NOT consumed
    ha_marker = os.path.join(tmproot, ".rabbit-human-approval-bypass")
    if os.path.exists(ha_marker):
        ok(".rabbit-human-approval-bypass preserved (not consumed)")
    else:
        fail_t(".rabbit-human-approval-bypass removed unexpectedly")

    # ---- E2E SCENARIO 2: second invocation does not leak skills-updated ----
    print()
    print("=== t2: second invocation does not re-emit consumed conditions ===")
    out2 = run_sync(tmproot)
    n2 = count_json_objects(out2)
    if n2 == 1:
        # session-override + human-approval still active; skills not
        obj2 = parse_one(out2)
        msg2 = obj2.get("systemMessage", "")
        if "Skills updated" not in msg2:
            ok("skills-updated did NOT re-emit on second invocation")
        else:
            fail_t(f"skills-updated leaked into 2nd invocation: {msg2!r}")
        if "SCOPE GUARD OFF" in msg2 and "HUMAN APPROVAL BYPASS" in msg2:
            ok("persistent markers (scope, human-approval) re-emit on second invocation")
        else:
            fail_t(f"persistent markers missing on 2nd invocation: {msg2!r}")
    else:
        fail_t(f"expected 1 JSON on 2nd invocation, got {n2}; raw: {out2!r}")

    # ---- E2E SCENARIO 3: one-time override consume-on-read ----
    print()
    print("=== t3: one-time override consumed exactly once when co-emitting ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-scope-override-used"), "a").close()
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()

    out = run_sync(tmproot)
    obj = parse_one(out)
    msg = obj.get("systemMessage", "")
    if "BYPASSED" in msg and "Skills updated" in msg:
        ok("scope-guard-bypass and skills-updated both emit")
    else:
        fail_t(f"missing line(s); msg={msg!r}")

    used = os.path.join(tmproot, ".rabbit-scope-override-used")
    if not os.path.exists(used):
        ok(".rabbit-scope-override-used consumed on emit")
    else:
        fail_t(".rabbit-scope-override-used not consumed")

    # second invocation: no JSON
    out2 = run_sync(tmproot)
    if out2.strip() == "":
        ok("no JSON on second invocation (all markers consumed)")
    else:
        fail_t(f"unexpected output on 2nd invocation: {out2!r}")

    # ---- E2E SCENARIO 4: zero-condition case ----
    print()
    print("=== t4: zero-condition case emits no JSON ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    out = run_sync(tmproot)
    if out.strip() == "":
        ok("no JSON emitted when no condition pending")
    else:
        fail_t(f"unexpected output for zero-condition: {out!r}")

    # ---- E2E SCENARIO 5: CLAUDE.md drift takes priority 1 and carries additionalContext ----
    print()
    print("=== t5: CLAUDE.md drift + skills-updated; drift line first; additionalContext present ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    # Corrupt CLAUDE.md to force drift
    claude_md = os.path.join(tmproot, "CLAUDE.md")
    with open(claude_md, "w") as f:
        f.write("# tampered\n")
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()

    out = run_sync(tmproot)
    n = count_json_objects(out)
    if n == 1:
        ok("one JSON object on drift + skills")
    else:
        fail_t(f"expected 1 JSON, got {n}; raw: {out!r}")
    obj = parse_one(out)
    msg = obj.get("systemMessage", "")
    if "Policy drift detected" in msg:
        ok("CLAUDE.md drift line present")
    else:
        fail_t(f"drift line missing: {msg!r}")
    if "Skills updated" in msg:
        ok("skills-updated line present in same JSON (aggregation works for drift too)")
    else:
        fail_t(f"skills line missing on drift+skills aggregation: {msg!r}")
    if "additionalContext" in obj and obj["additionalContext"]:
        ok("additionalContext present when CLAUDE.md drift is among conditions")
    else:
        fail_t(f"additionalContext missing on drift path; obj={obj!r}")

finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
