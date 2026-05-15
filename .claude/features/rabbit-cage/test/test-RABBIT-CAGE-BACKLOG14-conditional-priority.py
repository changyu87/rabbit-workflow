#!/usr/bin/env python3
"""Tests sync-check.py conditional-priority strategy (Spec Inv 37, 38)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
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


def make_clean_repo():
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", "main"], capture_output=True)

    os.makedirs(os.path.join(d, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(d, ".claude/features/policy"), exist_ok=True)

    for fname, content in [
        ("philosophy.md", "# Philosophy\nMachine First.\n"),
        ("spec-rules.md", "# Spec Rules\nSpec.\n"),
        ("coding-rules.md", "# Coding Rules\nCode.\n"),
    ]:
        with open(os.path.join(d, ".claude/features/policy", fname), "w") as f:
            f.write(content)

    with open(os.path.join(d, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test header"}, f)

    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts", fname),
            os.path.join(d, ".claude/features/rabbit-cage/scripts", fname),
        )

    with open(os.path.join(d, ".claude/features/registry.json"), "w") as f:
        json.dump({"schema_version": "1.0.0", "features": {}}, f)

    env = {**os.environ, "RABBIT_ROOT": d}
    result = subprocess.run([sys.executable, os.path.join(d, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
                            env=env, capture_output=True, text=True)
    with open(os.path.join(d, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")

    subprocess.run(["git", "-C", d, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return d


def run_sync(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    return subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True).stdout


print("test-RABBIT-CAGE-BACKLOG14-conditional-priority.py")
print("Asserting spec Invariants 37 and 38: conditional-priority strategy")
print()

tmproots = []
try:
    # t1
    print("=== t1: schema conformance — systemMessage always present when emitting ===")
    tmproot = make_clean_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()
    t1_output = run_sync(tmproot)
    has_sys_msg = "no"
    try:
        d = json.loads(t1_output)
        if "systemMessage" in d:
            has_sys_msg = "yes"
    except Exception:
        pass
    if has_sys_msg == "yes":
        ok("systemMessage field present in emitted JSON (Invariant 38)")
    else:
        fail_t(f"systemMessage field MISSING from emitted JSON — violates Invariant 38 (output: {t1_output!r})")

    # t2
    print("=== t2: no additionalContext on plugins-stale path (Invariant 38) ===")
    has_ctx = "no"
    try:
        d = json.loads(t1_output)
        if "additionalContext" in d:
            has_ctx = "yes"
    except Exception:
        pass
    if has_ctx == "no":
        ok("additionalContext absent on plugins-stale path (Invariant 38)")
    else:
        fail_t("additionalContext present on plugins-stale path — must only appear on CLAUDE.md paths (Invariant 38)")

    # t3
    print("=== t3: scope-guard-off suppresses skills-updated (Invariant 37, priority 3>4) ===")
    tmproot = make_clean_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()
    t3_output = run_sync(tmproot)
    t3_msg = extract_sys_msg(t3_output)
    t3_count = count_json_objects(t3_output)

    if t3_count == 1:
        ok("exactly one JSON object emitted when scope-guard-off AND skills-updated (Invariant 37)")
    else:
        fail_t(f"expected 1 JSON object, got {t3_count} — violates single-JSON invariant")

    if any(s in t3_msg.upper() for s in ("SCOPE GUARD", "OVERRIDE")) or "scope guard" in t3_msg or "override" in t3_msg:
        ok("scope-guard-off alert emitted (higher priority wins, Invariant 37)")
    else:
        fail_t(f"scope-guard-off alert NOT emitted — expected SCOPE GUARD message, got: {t3_msg!r}")

    if any(s in t3_msg for s in ("rabbit-refresh", "reload-plugins", "Skills updated")):
        fail_t("skills-updated alert leaked through — lower priority should be suppressed (Invariant 37)")
    else:
        ok("skills-updated suppressed when scope-guard-off active (Invariant 37)")

    # t4
    print("=== t4: scope-guard-bypass suppresses skills-updated (Invariant 37) ===")
    tmproot = make_clean_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-scope-override-used"), "a").close()
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "a").close()
    t4_output = run_sync(tmproot)
    t4_msg = extract_sys_msg(t4_output)
    t4_count = count_json_objects(t4_output)

    if t4_count == 1:
        ok("exactly one JSON object when scope-guard-bypass AND skills-updated")
    else:
        fail_t(f"expected 1 JSON object, got {t4_count}")

    msg_lower = t4_msg.lower()
    if any(s in msg_lower for s in ("bypassed", "bypass", "scope guard")):
        ok("scope-guard-bypass alert emitted (higher priority wins, Invariant 37)")
    else:
        fail_t(f"scope-guard-bypass alert NOT emitted — expected BYPASSED message, got: {t4_msg!r}")

    if any(s in t4_msg for s in ("rabbit-refresh", "reload-plugins", "Skills updated")):
        fail_t("skills-updated leaked through when scope-guard-bypass active (Invariant 37)")
    else:
        ok("skills-updated suppressed when scope-guard-bypass active (Invariant 37)")
finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

# t5
print("=== t5: spec.md declares conditional-priority strategy (Invariant 24f) ===")
spec_file = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
with open(spec_file) as f:
    spec_content = f.read()

if "conditional-priority" in spec_content:
    ok("spec.md contains 'conditional-priority' keyword (Invariant 24f)")
else:
    fail_t("spec.md does NOT contain 'conditional-priority' — strategy not declared in spec")

# t6
print("=== t6: spec.md declares all 4 priority conditions (Invariant 37) ===")
import re as _re
priority_count = 0
if _re.search(r"CLAUDE\.md drift", spec_content, _re.IGNORECASE):
    priority_count += 1
if _re.search(r"Surface drift|surface-drift", spec_content, _re.IGNORECASE):
    priority_count += 1
if _re.search(r"Scope-guard-off|scope guard off", spec_content, _re.IGNORECASE):
    priority_count += 1
if _re.search(r"Skills-updated|skills updated|skills-updated", spec_content, _re.IGNORECASE):
    priority_count += 1

if priority_count >= 4:
    ok("all 4 priority conditions referenced in spec (Invariant 37)")
else:
    fail_t(f"only {priority_count} of 4 priority conditions found in spec — Invariant 37 requires all 4 explicitly declared")

# t7
print("=== t7: contract.md declares sync-check-output schema (Invariant 38) ===")
contract_file = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/contract.md")
with open(contract_file) as f:
    contract_content = f.read()

if "sync-check-output" in contract_content:
    ok("contract.md contains 'sync-check-output' schema (Invariant 38)")
else:
    fail_t("contract.md does NOT declare 'sync-check-output' schema — violates machine-first requirement (Invariant 38)")

if "conditional-priority" in contract_content:
    ok("contract.md declares 'conditional-priority' strategy in schema (Invariant 38)")
else:
    fail_t("contract.md does NOT declare 'conditional-priority' strategy in schema")

if "priority_order" in contract_content:
    ok("contract.md includes priority_order field in schema")
else:
    fail_t("contract.md schema missing 'priority_order' field — schema is incomplete")

# t8
print("=== t8: spec.md contains Invariant 37 with priority order ===")
if _re.search(r"^37\.", spec_content, _re.MULTILINE):
    ok("Invariant 37 present in spec.md")
else:
    fail_t("Invariant 37 NOT found in spec.md — must be explicitly numbered per spec style")

if _re.search(r"^38\.", spec_content, _re.MULTILINE):
    ok("Invariant 38 present in spec.md")
else:
    fail_t("Invariant 38 NOT found in spec.md — output schema must be codified as invariant")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
