#!/usr/bin/env python3
"""test-check-script-backed.py — E2E for the script-backed-orchestration
scan script.

Drives scripts/check-script-backed.py as a subprocess against fixture feature
trees built under tempfile.TemporaryDirectory(), so the test never depends on
the live repo's contents. The script enforces the spec-rules §4 Script-Backed
Orchestration standard as a deterministic verify-or-flag DIMENSION.

Behaviours covered:

  t0: script exists and is executable.
  t1: a SKILL.md whose body carries a fenced bash block with a RUNTIME
      PLACEHOLDER (e.g. <feature-name>) is flagged with reason
      runtime-placeholder; the finding names file + line + snippet.
  t2: a fenced bash block that branches on a MODE-AWARE value (if/case
      branching) is flagged with reason mode-aware-branching.
  t3: a fenced bash block computing a value the body then assembles
      (command substitution / arithmetic) is flagged with reason
      computed-value.
  t4: a read-only informational one-liner (git log --oneline -5) is NOT
      flagged (the §4 read-only-informational exception), and a body that
      invokes a companion scripts/*.py is NOT flagged.
  t5: agents/*.md and commands/*.md bodies are scanned too (not just
      skills/*/SKILL.md).
  t6: a clean feature (no offending blocks) yields count == 0, findings == [],
      exit 0.
  t7: invocation error (missing subcommand / nonexistent feature-dir) exits 2.
  t8: a fenced bash block EXPLICITLY MARKED as a non-executable illustrative
      example (an `<!-- example -->` marker on the line directly above the
      opening fence) is SKIPPED even when it carries a runtime placeholder —
      illustrative invocation snippets do not self-flag.
  t9: the marker is NARROW: in a file mixing one marked example block with one
      UNMARKED live orchestration step that carries a placeholder, only the
      UNMARKED step is flagged. A live step with a placeholder STILL flags.
  t10: the real rabbit-housekeep SKILL.md (its own example invocation blocks
      marked illustrative) self-scans with ZERO findings.

Non-interactive. Exits non-zero on failure.

Version: 0.4.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "check-script-backed.py")

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


def run(*args):
    return subprocess.run(
        ["python3", SCRIPT, *args], capture_output=True, text=True
    )


def make_feature(tmp, skill_body=None, agent_body=None, command_body=None):
    """Build a minimal feature tree under tmp and return its dir."""
    feat = os.path.join(tmp, "feat")
    if skill_body is not None:
        d = os.path.join(feat, "skills", "feat")
        os.makedirs(d)
        with open(os.path.join(d, "SKILL.md"), "w") as f:
            f.write(skill_body)
    if agent_body is not None:
        d = os.path.join(feat, "agents")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "worker.md"), "w") as f:
            f.write(agent_body)
    if command_body is not None:
        d = os.path.join(feat, "commands")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "do.md"), "w") as f:
            f.write(command_body)
    return feat


PLACEHOLDER_BODY = """---
name: feat
---

# feat

Run the touch:

```bash
git checkout -B feat/<feature-name> origin/dev
python3 scripts/touch.py --feature <feature-name>
```
"""

MODE_BRANCH_BODY = """---
name: feat
---

# feat

Pick the path:

```bash
if [ "$MODE" = "plugin" ]; then
  target=.rabbit/.runtime
else
  target=.runtime
fi
echo "$target"
```
"""

COMPUTED_BODY = """---
name: feat
---

# feat

Compute the count:

```bash
n=$(ls .claude/features | wc -l)
echo "features: $n"
```
"""

CLEAN_BODY = """---
name: feat
---

# feat

Show recent history (read-only informational, allowed inline):

```bash
git log --oneline -5
```

The computed/branching logic lives in a companion script:

```bash
python3 .claude/features/feat/scripts/orchestrate.py run
```
"""

# A marked illustrative example: documents HOW to invoke a script, not a live
# orchestration step the model assembles. The `<!-- example -->` marker on the
# line directly above the opening fence exempts it.
MARKED_EXAMPLE_BODY = """---
name: feat
---

# feat

Here is how you would invoke the touch (illustrative only):

<!-- example -->
```bash
python3 scripts/touch.py --feature <feature-name>
```
"""

# A file mixing a marked illustrative example (with a placeholder) and an
# UNMARKED live orchestration step (also with a placeholder). Only the unmarked
# live step must flag — the marker must NOT weaken real detection.
MIXED_MARKER_BODY = """---
name: feat
---

# feat

Example invocation (illustrative, not a live step):

<!-- example -->
```bash
python3 scripts/touch.py --feature <feature-name>
```

Now run the live step:

```bash
git checkout -B feat/<branch-name> origin/dev
```
"""


# t0
if not (os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK)):
    fail("t0", f"missing or non-executable: {SCRIPT}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "check-script-backed.py exists and is executable")


def reasons_for(data, suffix):
    return [
        f["reason"] for f in data.get("findings", [])
        if f.get("file", "").endswith(suffix)
    ]


# t1: runtime placeholder flagged
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=PLACEHOLDER_BODY)
    r = run("scan", feat)
    if r.returncode != 0:
        fail("t1", f"scan exited {r.returncode}; stderr={r.stderr}")
    else:
        data = json.loads(r.stdout)
        rs = reasons_for(data, "SKILL.md")
        finding = next(
            (f for f in data["findings"] if f["file"].endswith("SKILL.md")),
            None,
        )
        if ("runtime-placeholder" in rs and finding
                and isinstance(finding.get("line"), int)
                and finding.get("snippet")):
            ok("t1", "runtime-placeholder bash block flagged with file/line/snippet")
        else:
            fail("t1", f"expected runtime-placeholder finding; data={data}")

# t2: mode-aware branching flagged
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=MODE_BRANCH_BODY)
    r = run("scan", feat)
    data = json.loads(r.stdout)
    if r.returncode == 0 and "mode-aware-branching" in reasons_for(data, "SKILL.md"):
        ok("t2", "mode-aware-branching bash block flagged")
    else:
        fail("t2", f"expected mode-aware-branching finding; rc={r.returncode}; data={data}")

# t3: computed value flagged
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=COMPUTED_BODY)
    r = run("scan", feat)
    data = json.loads(r.stdout)
    if r.returncode == 0 and "computed-value" in reasons_for(data, "SKILL.md"):
        ok("t3", "computed-value bash block flagged")
    else:
        fail("t3", f"expected computed-value finding; rc={r.returncode}; data={data}")

# t4: read-only informational + script-backed invocation NOT flagged
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=CLEAN_BODY)
    r = run("scan", feat)
    data = json.loads(r.stdout)
    if r.returncode == 0 and data.get("count") == 0 and data.get("findings") == []:
        ok("t4", "read-only one-liner and script-backed invocation not flagged")
    else:
        fail("t4", f"expected zero findings; rc={r.returncode}; data={data}")

# t5: agents/*.md and commands/*.md scanned too
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(
        tmp, agent_body=PLACEHOLDER_BODY, command_body=COMPUTED_BODY
    )
    r = run("scan", feat)
    data = json.loads(r.stdout)
    agent_flagged = "runtime-placeholder" in reasons_for(data, "worker.md")
    command_flagged = "computed-value" in reasons_for(data, "do.md")
    if r.returncode == 0 and agent_flagged and command_flagged:
        ok("t5", "agents/*.md and commands/*.md bodies are scanned")
    else:
        fail("t5", f"expected agent+command findings; rc={r.returncode}; data={data}")

# t6: clean feature -> count 0, exit 0
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=CLEAN_BODY, agent_body=CLEAN_BODY)
    r = run("scan", feat)
    data = json.loads(r.stdout)
    if r.returncode == 0 and data["count"] == 0:
        ok("t6", "clean feature yields count 0 and exit 0")
    else:
        fail("t6", f"expected clean scan; rc={r.returncode}; data={data}")

# t7: invocation errors exit 2
r1 = run("bogus", "x")
r2 = run("scan", os.path.join(tempfile.gettempdir(), "no-such-feature-dir-xyz"))
r3 = run()
if r1.returncode == 2 and r2.returncode == 2 and r3.returncode == 2:
    ok("t7", "invocation errors exit 2")
else:
    fail("t7", f"expected exit 2; got {r1.returncode}, {r2.returncode}, {r3.returncode}")

# t8: a marked illustrative example with a placeholder is SKIPPED
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=MARKED_EXAMPLE_BODY)
    r = run("scan", feat)
    data = json.loads(r.stdout)
    if r.returncode == 0 and data.get("count") == 0 and data.get("findings") == []:
        ok("t8", "marked illustrative example block is skipped (not flagged)")
    else:
        fail("t8", f"expected zero findings for marked example; rc={r.returncode}; data={data}")

# t9: marker is NARROW — only the unmarked live step flags
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, skill_body=MIXED_MARKER_BODY)
    r = run("scan", feat)
    data = json.loads(r.stdout)
    findings = data.get("findings", [])
    only_live = (
        data.get("count") == 1
        and len(findings) == 1
        and findings[0]["reason"] == "runtime-placeholder"
        and "<branch-name>" in findings[0]["snippet"]
    )
    if r.returncode == 0 and only_live:
        ok("t9", "marker is narrow: unmarked live step with placeholder STILL flags")
    else:
        fail("t9", f"expected exactly one finding (the live step); rc={r.returncode}; data={data}")

# t10: the real rabbit-housekeep SKILL.md self-scans with ZERO findings
REAL_FEATURE_DIR = FEATURE_DIR
r = run("scan", REAL_FEATURE_DIR)
data = json.loads(r.stdout)
if r.returncode == 0 and data.get("count") == 0 and data.get("findings") == []:
    ok("t10", "real rabbit-housekeep SKILL.md self-scans with zero findings")
else:
    fail("t10", f"expected zero self-findings; rc={r.returncode}; data={data}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
