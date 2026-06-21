#!/usr/bin/env python3
"""test-user-facing-surface.py — E2E for the rabbit-housekeep user-facing
invocation surface and consuming-project scope resolution (issue #1179).

rabbit-housekeep must be invocable by a consumer as a slash command, and the
housekeeping wave it runs must anchor on the CONSUMING PROJECT's declared
features — `rabbit-project/features/*` in a vendored install — NOT on
rabbit-workflow's own framework features under `.claude/features/*`.

Asserts, against the real feature tree:

  c0: commands/rabbit-housekeep.md exists and is non-empty.
  c1: the command file carries YAML frontmatter with all six required keys
      (name, description, version, owner, deprecation_criterion,
      template_version), owner == "rabbit-workflow team", and
      name == rabbit-housekeep.
  c2: feature.json manifest declares a publish_command entry sourcing
      commands/rabbit-housekeep.md, AND the command version matches the
      feature version (lockstep), AND the surface.commands list names it.

  s0: scripts/resolve-housekeep-scope.py exists.
  s1: in VENDORED mode it enumerates the consuming project's features
      (a feature placed under <root>/rabbit-project/features/<name>) and does
      NOT return rabbit-workflow's own framework features under
      <root>/.claude/features/<name>.
  s2: in STANDALONE mode it enumerates the project's features under
      <root>/.claude/features/<name>.
  s3: bad invocation exits non-zero.

  k0: the SKILL.md documents that the wave targets the CONSUMING PROJECT (not
      rabbit's self-repo) and references the scope-resolution script.

Non-interactive. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
COMMAND_MD = os.path.join(FEATURE_DIR, "commands", "rabbit-housekeep.md")
SCOPE_SCRIPT = os.path.join(
    FEATURE_DIR, "scripts", "resolve-housekeep-scope.py"
)
SKILL_MD = os.path.join(
    FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md"
)

REQUIRED_KEYS = (
    "name",
    "description",
    "version",
    "owner",
    "deprecation_criterion",
    "template_version",
)
REQUIRED_OWNER = "rabbit-workflow team"

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


def frontmatter_keys(text):
    m = re.search(r"(?ms)\A---\s*\n(.*?)\n---\s*\n", text)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            out[km.group(1)] = km.group(2).strip().strip('"').strip("'")
    return out


with open(FEATURE_JSON, encoding="utf-8") as f:
    fjson = json.load(f)
feature_version = fjson.get("version", "")

# c0
if not (os.path.isfile(COMMAND_MD) and os.path.getsize(COMMAND_MD) > 0):
    fail("c0", f"missing or empty: {COMMAND_MD}")
else:
    ok("c0", "commands/rabbit-housekeep.md exists and is non-empty")

cmd_keys = None
if os.path.isfile(COMMAND_MD):
    with open(COMMAND_MD, encoding="utf-8") as f:
        cmd_text = f.read()
    cmd_keys = frontmatter_keys(cmd_text)

# c1
if cmd_keys is None:
    fail("c1", "command file has no YAML frontmatter block")
else:
    missing = [k for k in REQUIRED_KEYS if not cmd_keys.get(k)]
    problems = []
    if missing:
        problems.append(f"missing keys {missing}")
    if cmd_keys.get("owner") != REQUIRED_OWNER:
        problems.append(f"owner={cmd_keys.get('owner')!r}")
    if cmd_keys.get("name") != "rabbit-housekeep":
        problems.append(f"name={cmd_keys.get('name')!r}")
    if problems:
        fail("c1", f"frontmatter problems: {problems}")
    else:
        ok("c1", "command frontmatter has all required keys, correct "
                 "owner and name")

# c2: manifest publishes the command, lockstep version, surface lists it
manifest = fjson.get("manifest", [])
published_cmd = any(
    m.get("api") == "publish_command"
    and m.get("args", {}).get("source") == "commands/rabbit-housekeep.md"
    for m in manifest
)
surface_cmds = fjson.get("surface", {}).get("commands", []) or []
surface_lists = "commands/rabbit-housekeep.md" in surface_cmds
version_lockstep = bool(cmd_keys) and cmd_keys.get("version") == feature_version
if published_cmd and surface_lists and version_lockstep:
    ok("c2", "manifest publish_command + surface.commands + version lockstep")
else:
    fail("c2", "manifest/surface/version problem "
               f"(published={published_cmd}, surface={surface_lists}, "
               f"version_lockstep={version_lockstep}, "
               f"cmd_version={cmd_keys.get('version') if cmd_keys else None}, "
               f"feature_version={feature_version})")

# s0
if not os.path.isfile(SCOPE_SCRIPT):
    fail("s0", f"missing: {SCOPE_SCRIPT}")
else:
    ok("s0", "scripts/resolve-housekeep-scope.py exists")


def run_scope(root, *extra):
    return subprocess.run(
        ["python3", SCOPE_SCRIPT, "list", "--root", root, *extra],
        capture_output=True, text=True,
    )


def make_feature(base, name):
    d = os.path.join(base, "features", name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "feature.json"), "w") as f:
        json.dump({"name": name}, f)


# s1: vendored mode targets the consuming project, not rabbit's own features.
if os.path.isfile(SCOPE_SCRIPT):
    with tempfile.TemporaryDirectory() as tmp:
        # rabbit's OWN framework feature (must NOT be returned in vendored mode)
        os.makedirs(os.path.join(tmp, ".claude"), exist_ok=True)
        make_feature(os.path.join(tmp, ".claude"), "rabbit-cage")
        # the CONSUMING PROJECT's feature
        make_feature(os.path.join(tmp, "rabbit-project"), "user-auth")
        # vendored-mode marker
        os.makedirs(os.path.join(tmp, ".runtime"), exist_ok=True)
        with open(os.path.join(tmp, ".runtime", "mode"), "w") as f:
            f.write("vendored")
        r = run_scope(tmp)
        names = set(r.stdout.split())
        if r.returncode == 0 and "user-auth" in names and \
                "rabbit-cage" not in names:
            ok("s1", "vendored mode returns consuming-project features only "
                     f"({sorted(names)})")
        else:
            fail("s1", "vendored scope resolution must return the consuming "
                       "project's features and EXCLUDE rabbit's own "
                       f"(rc={r.returncode}, names={sorted(names)}, "
                       f"stderr={r.stderr.strip()})")

# s2: standalone mode targets .claude/features
if os.path.isfile(SCOPE_SCRIPT):
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, ".claude"), exist_ok=True)
        make_feature(os.path.join(tmp, ".claude"), "user-auth")
        r = run_scope(tmp)
        names = set(r.stdout.split())
        if r.returncode == 0 and "user-auth" in names:
            ok("s2", f"standalone mode returns .claude/features ({sorted(names)})")
        else:
            fail("s2", "standalone scope resolution must return "
                       ".claude/features/* "
                       f"(rc={r.returncode}, names={sorted(names)}, "
                       f"stderr={r.stderr.strip()})")

# s3: bad invocation exits non-zero
if os.path.isfile(SCOPE_SCRIPT):
    r = subprocess.run(
        ["python3", SCOPE_SCRIPT, "bogus-subcommand"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        ok("s3", f"bad invocation exits non-zero (rc={r.returncode})")
    else:
        fail("s3", "bad invocation must exit non-zero")

# k0: SKILL.md documents consuming-project targeting + scope script
if os.path.isfile(SKILL_MD):
    with open(SKILL_MD, encoding="utf-8") as f:
        skill_text = f.read()
    mentions_project = re.search(r"consuming project", skill_text, re.IGNORECASE)
    mentions_script = "resolve-housekeep-scope.py" in skill_text
    if mentions_project and mentions_script:
        ok("k0", "SKILL.md documents consuming-project targeting + scope script")
    else:
        fail("k0", "SKILL.md must document the wave targets the consuming "
                   "project and reference resolve-housekeep-scope.py "
                   f"(project={bool(mentions_project)}, "
                   f"script={mentions_script})")
else:
    fail("k0", f"missing: {SKILL_MD}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
