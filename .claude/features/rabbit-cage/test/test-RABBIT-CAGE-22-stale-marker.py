#!/usr/bin/env python3
"""Tests for RABBIT-CAGE-22/24: .rabbit-skills-updated marker model."""
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
SESSION_INIT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")
BUILD_SH = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/build.py")

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


def make_build_repo():
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
    result = subprocess.run(
        [sys.executable, os.path.join(d, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
        env=env, capture_output=True, text=True,
    )
    with open(os.path.join(d, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")

    subprocess.run(["git", "-C", d, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return d


def make_contract(d, targets):
    os.makedirs(os.path.join(d, ".claude/features/contract"), exist_ok=True)
    contract = {
        "schema_version": "1.0.0",
        "owner": "test",
        "deprecation_criterion": "test",
        "updated": "2026-01-01",
        "targets": targets,
    }
    with open(os.path.join(d, ".claude/features/contract/build-contract.json"), "w") as f:
        json.dump(contract, f, indent=2)


def run_build(tmproot):
    subprocess.run([sys.executable, BUILD_SH, tmproot], capture_output=True)


print("test-RABBIT-CAGE-22-stale-marker.py")
print()

tmproot = make_build_repo()

try:
    # t1
    print("=== t1: build.py writes .rabbit-skills-updated for .claude/skills/*/SKILL.md target ===")
    os.makedirs(os.path.join(tmproot, ".claude/features/test-skill/skills/test-skill"), exist_ok=True)
    with open(os.path.join(tmproot, ".claude/features/test-skill/skills/test-skill/SKILL.md"), "w") as f:
        f.write("# Test skill\n")
    make_contract(tmproot, [{"name": "skills/test-skill/SKILL.md", "type": "copy-file",
                             "source": ".claude/features/test-skill/skills/test-skill/SKILL.md",
                             "destination": ".claude/skills/test-skill/SKILL.md"}])
    marker = os.path.join(tmproot, ".rabbit-skills-updated")
    if os.path.isfile(marker):
        os.remove(marker)
    run_build(tmproot)
    if os.path.isfile(marker):
        ok("build.py wrote .rabbit-skills-updated after copying a SKILL.md target")
    else:
        fail_t("build.py did NOT write .rabbit-skills-updated after copying a SKILL.md target")

    # t2
    print("=== t2: .rabbit-skills-updated contains the skill name ===")
    if os.path.isfile(marker):
        with open(marker) as f:
            content = f.read()
        if "test-skill" in content:
            ok(".rabbit-skills-updated contains skill name 'test-skill'")
        else:
            fail_t(f".rabbit-skills-updated does NOT contain 'test-skill' (content: {content!r})")
    else:
        fail_t(".rabbit-skills-updated missing (covered by t1)")

    # t3
    print("=== t3: build.py does NOT write .rabbit-skills-updated for .claude/commands/ target ===")
    os.makedirs(os.path.join(tmproot, ".claude/features/rabbit-cage/commands"), exist_ok=True)
    with open(os.path.join(tmproot, ".claude/features/rabbit-cage/commands/test-cmd.md"), "w") as f:
        f.write("# Test cmd\n")
    make_contract(tmproot, [{"name": "commands/test-cmd.md", "type": "copy-file",
                             "source": ".claude/features/rabbit-cage/commands/test-cmd.md",
                             "destination": ".claude/commands/test-cmd.md"}])
    if os.path.isfile(marker):
        os.remove(marker)
    run_build(tmproot)
    if os.path.isfile(marker):
        fail_t("build.py incorrectly wrote .rabbit-skills-updated for a commands target")
    else:
        ok("build.py did NOT write .rabbit-skills-updated for a commands target")

    # t4
    print("=== t4: build.py does NOT write .rabbit-skills-updated for non-skills copy target ===")
    with open(os.path.join(tmproot, "source-readme.md"), "w") as f:
        f.write("# README\n")
    make_contract(tmproot, [{"name": "README.md", "type": "copy-file",
                             "source": "source-readme.md", "destination": "README.md"}])
    if os.path.isfile(marker):
        os.remove(marker)
    run_build(tmproot)
    if os.path.isfile(marker):
        fail_t("build.py incorrectly wrote .rabbit-skills-updated for a non-skills target")
    else:
        ok("build.py did NOT write .rabbit-skills-updated for a non-skills target")

    # t5
    print("=== t5: build.py appends multiple skill names for multiple SKILL.md targets ===")
    os.makedirs(os.path.join(tmproot, ".claude/features/feat-a/skills/feat-a"), exist_ok=True)
    os.makedirs(os.path.join(tmproot, ".claude/features/feat-b/skills/feat-b"), exist_ok=True)
    with open(os.path.join(tmproot, ".claude/features/feat-a/skills/feat-a/SKILL.md"), "w") as f:
        f.write("# Feat A\n")
    with open(os.path.join(tmproot, ".claude/features/feat-b/skills/feat-b/SKILL.md"), "w") as f:
        f.write("# Feat B\n")
    make_contract(tmproot, [
        {"name": "skills/feat-a/SKILL.md", "type": "copy-file",
         "source": ".claude/features/feat-a/skills/feat-a/SKILL.md",
         "destination": ".claude/skills/feat-a/SKILL.md"},
        {"name": "skills/feat-b/SKILL.md", "type": "copy-file",
         "source": ".claude/features/feat-b/skills/feat-b/SKILL.md",
         "destination": ".claude/skills/feat-b/SKILL.md"},
    ])
    if os.path.isfile(marker):
        os.remove(marker)
    run_build(tmproot)
    if os.path.isfile(marker):
        with open(marker) as f:
            content = f.read()
        if "feat-a" in content and "feat-b" in content:
            ok(".rabbit-skills-updated contains both skill names")
        else:
            fail_t(f".rabbit-skills-updated missing skill names (content: {content!r})")
    else:
        fail_t("build.py did NOT write .rabbit-skills-updated for multiple SKILL.md targets")

    # t6
    print("=== t6: session-init.py does NOT reference .rabbit-plugins-stale ===")
    with open(SESSION_INIT) as f:
        si = f.read()
    if ".rabbit-plugins-stale" in si:
        fail_t("session-init.py still references .rabbit-plugins-stale — must be removed")
    else:
        ok("session-init.py has no .rabbit-plugins-stale reference")

    # t7
    print("=== t7: sync-check.py does NOT reference .rabbit-plugins-stale ===")
    with open(SYNC_CHECK) as f:
        sc = f.read()
    if ".rabbit-plugins-stale" in sc:
        fail_t("sync-check.py still references .rabbit-plugins-stale — must be removed")
    else:
        ok("sync-check.py has no .rabbit-plugins-stale reference")
finally:
    shutil.rmtree(tmproot, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
