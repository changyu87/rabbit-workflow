#!/usr/bin/env python3
"""BACKLOG-18 aggregation strategy (Inv 37, 38).

Replaces the conditional-priority assertions that previously lived in
test-RABBIT-CAGE-BACKLOG14-conditional-priority.py. Aggregation means EVERY
pending condition emits its line within a single JSON object; the priority
order controls ORDERING, not suppression.
"""
import json
import os
import shutil
import sys

from test_helpers import REPO_ROOT, make_git_repo, run_sync

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


def extract_sys_msg(output):
    try:
        d = json.loads(output)
        return d.get("systemMessage", "")
    except Exception:
        return ""


def count_json_objects(data):
    data = data.strip()
    if not data:
        return 0
    try:
        json.loads(data)
        return 1
    except Exception:
        pass
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
            idx += (len(data) - len(data[idx:])) + end
        except Exception:
            break
    return count


print("test-RABBIT-CAGE-BACKLOG-18-aggregation.py")
print("Asserting Inv 37 / 38: aggregation strategy (no suppression)")
print()

tmproots = []
try:
    # t1: scope-guard-off + skills-updated BOTH emit (was: one suppressed)
    print("=== t1: scope-guard-off + skills-updated BOTH emit (Inv 37) ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()
    out = run_sync(tmproot)
    n = count_json_objects(out)
    msg = extract_sys_msg(out)

    if n == 1:
        ok("exactly one JSON object emitted (single-emission contract)")
    else:
        fail_t(f"expected 1 JSON object, got {n} (output: {out!r})")

    if "SCOPE GUARD OFF" in msg:
        ok("scope-guard-off line present in aggregated systemMessage")
    else:
        fail_t(f"scope-guard-off line missing from aggregated systemMessage: {msg!r}")

    if "Skills updated" in msg:
        ok("skills-updated line ALSO present (no suppression — Inv 37 aggregation)")
    else:
        fail_t(f"skills-updated line missing — should aggregate, not suppress: {msg!r}")

    # t2: ordering — scope-guard (priority 3) before skills-updated (priority 5)
    print()
    print("=== t2: aggregated lines in Inv 37 priority order ===")
    idx_scope = msg.find("SCOPE GUARD OFF")
    idx_skills = msg.find("Skills updated")
    if 0 <= idx_scope < idx_skills:
        ok("scope-guard line appears BEFORE skills line (priority 3 before 5)")
    else:
        fail_t(f"priority ordering violated; scope-idx={idx_scope} skills-idx={idx_skills}")

    # t3: scope-guard-bypass + skills-updated aggregate
    print()
    print("=== t3: scope-guard-bypass + skills-updated BOTH emit ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-scope-override-used"), "a").close()
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()
    out = run_sync(tmproot)
    n = count_json_objects(out)
    msg = extract_sys_msg(out)

    if n == 1:
        ok("one JSON object when scope-guard-bypass + skills-updated")
    else:
        fail_t(f"expected 1 JSON, got {n}")
    if "BYPASSED" in msg:
        ok("scope-guard-bypass line present")
    else:
        fail_t(f"bypass line missing: {msg!r}")
    if "Skills updated" in msg:
        ok("skills line present (aggregation, not suppression)")
    else:
        fail_t(f"skills line missing: {msg!r}")

    # t4: human-approval + skills-updated aggregate (priority 4 + 5)
    print()
    print("=== t4: human-approval-bypass + skills-updated BOTH emit ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()
    out = run_sync(tmproot)
    n = count_json_objects(out)
    msg = extract_sys_msg(out)

    if n == 1:
        ok("one JSON object")
    else:
        fail_t(f"expected 1 JSON, got {n}")
    if "HUMAN APPROVAL BYPASS" in msg:
        ok("human-approval line present")
    else:
        fail_t(f"human-approval missing: {msg!r}")
    if "Skills updated" in msg:
        ok("skills line present (aggregation)")
    else:
        fail_t(f"skills line missing: {msg!r}")
    idx_ha = msg.find("HUMAN APPROVAL BYPASS")
    idx_sk = msg.find("Skills updated")
    if 0 <= idx_ha < idx_sk:
        ok("priority order: human-approval (4) before skills (5)")
    else:
        fail_t(f"order wrong; ha={idx_ha} sk={idx_sk}")
finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

# t-spec: spec.md declares aggregation
print()
print("=== t-spec: spec.md declares aggregation strategy ===")
spec_file = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
with open(spec_file) as f:
    spec_content = f.read()

if "aggregation" in spec_content:
    ok("spec.md mentions 'aggregation' strategy")
else:
    fail_t("spec.md does NOT mention 'aggregation' strategy")

import re as _re
if _re.search(r"^37\.", spec_content, _re.MULTILINE):
    ok("Invariant 37 still present in spec.md")
else:
    fail_t("Invariant 37 missing from spec.md")

if _re.search(r"^38\.", spec_content, _re.MULTILINE):
    ok("Invariant 38 still present in spec.md")
else:
    fail_t("Invariant 38 missing from spec.md")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
