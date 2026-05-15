#!/usr/bin/env python3
"""Tests for RABBIT-CAGE-BUG-4: build-targets.py sha256-gated marker writes."""
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
    result = subprocess.run([sys.executable, os.path.join(d, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
                            env=env, capture_output=True, text=True)
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


print("test-RABBIT-CAGE-BUG4.py")
print()

tmproot = make_build_repo()
try:
    os.makedirs(os.path.join(tmproot, ".claude/features/test-skill/skills/test-skill"), exist_ok=True)
    SRC = os.path.join(tmproot, ".claude/features/test-skill/skills/test-skill/SKILL.md")
    DEST = os.path.join(tmproot, ".claude/skills/test-skill/SKILL.md")
    MARKER = os.path.join(tmproot, ".rabbit-skills-updated")
    with open(SRC, "w") as f:
        f.write("# Test skill v1\nbody\n")
    make_contract(tmproot, [{"name": "skills/test-skill/SKILL.md", "type": "copy-file",
                             "source": ".claude/features/test-skill/skills/test-skill/SKILL.md",
                             "destination": ".claude/skills/test-skill/SKILL.md"}])

    # t1
    print("=== t1: destination absent → marker IS written ===")
    if os.path.isfile(MARKER):
        os.remove(MARKER)
    if os.path.isfile(DEST):
        os.remove(DEST)
    run_build(tmproot)
    if os.path.isfile(MARKER):
        ok("marker written when destination did not exist")
    else:
        fail_t("marker NOT written when destination did not exist (first build must mark)")

    # t2
    print("=== t2: destination identical to source → marker NOT written ===")
    if os.path.isfile(MARKER):
        os.remove(MARKER)
    run_build(tmproot)
    if os.path.isfile(MARKER):
        os.remove(MARKER)
    run_build(tmproot)
    if os.path.isfile(MARKER):
        fail_t("marker WAS written on no-op build (source == destination); BUG-4 not fixed")
    else:
        ok("marker NOT written when source and destination are byte-identical")

    # t3
    print("=== t3: destination differs from source → marker IS written ===")
    with open(SRC, "w") as f:
        f.write("# Test skill v2\nbody changed\n")
    if os.path.isfile(MARKER):
        os.remove(MARKER)
    run_build(tmproot)
    if os.path.isfile(MARKER):
        ok("marker written when source content changed")
    else:
        fail_t("marker NOT written when source content actually changed")
finally:
    shutil.rmtree(tmproot, ignore_errors=True)

print()
print(f"Total: {total}  Failures: {failures}")
sys.exit(1 if failures else 0)
