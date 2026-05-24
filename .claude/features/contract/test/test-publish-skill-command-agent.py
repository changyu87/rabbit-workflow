#!/usr/bin/env python3
"""test-publish-skill-command-agent.py — exercises publish_skill, publish_command,
publish_agent: path-convention variants of publish_file.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_skill, publish_command, publish_agent  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# --- publish_skill ---

# t1: skill deployed to .claude/skills/<name>/SKILL.md; name from parent dir
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    skill_src = os.path.join(feat, "skills", "rabbit-foo")
    os.makedirs(skill_src)
    with open(os.path.join(skill_src, "SKILL.md"), "w") as f:
        f.write("# rabbit-foo skill\n")
    r = publish_skill("skills/rabbit-foo/SKILL.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "skills", "rabbit-foo", "SKILL.md")
    if not r.passed:
        fail(f"t1: publish_skill failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail(f"t1: skill not at {dest}")
    elif open(dest).read() != "# rabbit-foo skill\n":
        fail("t1: skill content mismatch")
    else:
        ok("t1: publish_skill deploys to .claude/skills/<name>/SKILL.md")

# t2: skill name derived from source parent directory name
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    skill_src = os.path.join(feat, "skills", "rabbit-bar")
    os.makedirs(skill_src)
    with open(os.path.join(skill_src, "SKILL.md"), "w") as f:
        f.write("bar")
    publish_skill("skills/rabbit-bar/SKILL.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "skills", "rabbit-bar", "SKILL.md")
    if os.path.isfile(dest):
        ok("t2: skill name derived from source parent directory name")
    else:
        fail(f"t2: expected {dest}")

# t3: missing source → passed=False
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_skill("skills/rabbit-missing/SKILL.md", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t3: missing source should fail")
    else:
        ok("t3: publish_skill missing source → passed=False")

# t4: idempotent — same content reports no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    skill_src = os.path.join(feat, "skills", "rabbit-baz")
    skill_dst = os.path.join(root, ".claude", "skills", "rabbit-baz")
    os.makedirs(skill_src)
    os.makedirs(skill_dst)
    content = "# rabbit-baz\n"
    with open(os.path.join(skill_src, "SKILL.md"), "w") as f:
        f.write(content)
    with open(os.path.join(skill_dst, "SKILL.md"), "w") as f:
        f.write(content)
    r = publish_skill("skills/rabbit-baz/SKILL.md", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t4: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t4: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t4: publish_skill idempotent when content unchanged")

# --- publish_command ---

# t5: command deployed to .claude/commands/<basename>
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    cmd_dir = os.path.join(feat, "commands")
    os.makedirs(cmd_dir)
    with open(os.path.join(cmd_dir, "rabbit-do.md"), "w") as f:
        f.write("# rabbit-do\n")
    r = publish_command("commands/rabbit-do.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "commands", "rabbit-do.md")
    if not r.passed:
        fail(f"t5: publish_command failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail(f"t5: command not at {dest}")
    else:
        ok("t5: publish_command deploys to .claude/commands/<basename>")

# t6: command idempotent
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    cmd_dir = os.path.join(feat, "commands")
    dest_dir = os.path.join(root, ".claude", "commands")
    os.makedirs(cmd_dir)
    os.makedirs(dest_dir)
    with open(os.path.join(cmd_dir, "rabbit-x.md"), "w") as f:
        f.write("same")
    with open(os.path.join(dest_dir, "rabbit-x.md"), "w") as f:
        f.write("same")
    r = publish_command("commands/rabbit-x.md", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t6: idempotent command failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t6: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t6: publish_command idempotent when content unchanged")

# --- publish_agent ---

# t7: agent deployed to .claude/agents/<basename>
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    agent_dir = os.path.join(feat, "agents")
    os.makedirs(agent_dir)
    with open(os.path.join(agent_dir, "rabbit-helper.md"), "w") as f:
        f.write("# rabbit-helper agent\n")
    r = publish_agent("agents/rabbit-helper.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "agents", "rabbit-helper.md")
    if not r.passed:
        fail(f"t7: publish_agent failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail(f"t7: agent not at {dest}")
    else:
        ok("t7: publish_agent deploys to .claude/agents/<basename>")

# t8: agent missing source → passed=False
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_agent("agents/rabbit-missing.md", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t8: missing agent source should fail")
    else:
        ok("t8: publish_agent missing source → passed=False")

if FAIL:
    print("test-publish-skill-command-agent: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-skill-command-agent: all checks passed.")
