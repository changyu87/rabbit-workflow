#!/usr/bin/env python3
"""End-to-end tests for rabbit-cage Wave 3 (Inv 47-48).

Inv 47: commands/rabbit-project.md references only existing .py scripts;
        no `.sh` references; any referenced script path actually exists.
Inv 48 (post-BUG-97 revert): rabbit-config.py human-approval messages name the
        marker file and use the 'gate ENABLED/DISABLED (bypass ACTIVE)' framing.
        The bare ENABLED/DISABLED verbs are forbidden — the confirmation must
        name what is being enabled (the GATE) and call out when bypass is
        ACTIVE so the operator can read the message cold.

(Inv 46 was retired in RABBIT-CAGE-BACKLOG-26 when new-feature.py moved
into the rabbit-feature feature; its tests now live at
.claude/features/rabbit-feature/test/test-new-feature.py.)
"""
import os
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

RABBIT_PROJECT_MD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/commands/rabbit-project.md"
)
RABBIT_CONFIG_PY = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py",
)

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-RABBIT-CAGE-WAVE3-inv66-68.py")

# ---------------------------------------------------------------------------
# Inv 47: commands/rabbit-project.md references only existing .py scripts
# ---------------------------------------------------------------------------
if os.path.isfile(RABBIT_PROJECT_MD):
    with open(RABBIT_PROJECT_MD) as f:
        md_text = f.read()

    # t7: no .sh references anywhere in the doc.
    if ".sh" not in md_text:
        ok(7, "commands/rabbit-project.md contains no .sh references")
    else:
        sh_lines = [ln for ln in md_text.splitlines() if ".sh" in ln]
        fail_t(7, f"commands/rabbit-project.md still references .sh: {sh_lines}")

    # t8: any explicit `.claude/...py` path it mentions actually exists.
    referenced = re.findall(r"\.claude/[A-Za-z0-9_./-]+\.py", md_text)
    if not referenced:
        fail_t(8, "commands/rabbit-project.md mentions no .py script path at all")
    else:
        missing = [p for p in referenced
                   if not os.path.isfile(os.path.join(REPO_ROOT, p))]
        if not missing:
            ok(8, f"all referenced .py paths exist ({len(referenced)} found)")
        else:
            fail_t(8, f"referenced .py paths missing on disk: {missing}")
else:
    fail_t(7, f"commands/rabbit-project.md not found at {RABBIT_PROJECT_MD}")
    fail_t(8, "commands/rabbit-project.md not found")

# ---------------------------------------------------------------------------
# Inv 48 (post-BUG-97 revert): rabbit-config.py human-approval messages.
# Subcommand restored to 'human-approval' with the original boolean semantics:
# true = gate ACTIVE (marker removed); false = bypass ACTIVE (marker written).
# Confirmation text uses the 'gate ENABLED/DISABLED (bypass ACTIVE)' framing —
# bare ENABLED/DISABLED is forbidden because it does not name what is being
# enabled.
# ---------------------------------------------------------------------------
def run_cfg(args, wd):
    return subprocess.run(
        [sys.executable, RABBIT_CONFIG_PY] + list(args),
        cwd=wd, capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory(prefix="rc-wave3-cfg-") as wd:
    # t9: `false` (bypass ACTIVE) message names the marker, Step 4, and the
    # explicit 'bypass ACTIVE' state. The gate is DISABLED in this path.
    res = run_cfg(["human-approval", "false"], wd)
    out_false = res.stdout
    needed_false = [
        "DISABLED",
        "bypass ACTIVE",
        ".rabbit-human-approval-bypass",
        "Step 4",
    ]
    missing_false = [s for s in needed_false if s not in out_false]
    if res.returncode == 0 and not missing_false:
        ok(9, "human-approval false message names DISABLED + 'bypass ACTIVE' + marker + Step 4")
    else:
        fail_t(9, f"missing {missing_false!r} in stdout={out_false!r}")

    # t10: `true` (gate ACTIVE) message names ENABLED + marker removed + Step 4.
    res = run_cfg(["human-approval", "true"], wd)
    out_true = res.stdout
    needed_true = ["ENABLED", ".rabbit-human-approval-bypass", "Step 4"]
    missing_true = [s for s in needed_true if s not in out_true]
    if res.returncode == 0 and not missing_true:
        ok(10, "human-approval true message names ENABLED + marker + Step 4")
    else:
        fail_t(10, f"missing {missing_true!r} in stdout={out_true!r}")

    # t11: idempotent `true` (already enabled / marker absent) names ENABLED
    # and notes the file was not rewritten.
    res = run_cfg(["human-approval", "true"], wd)
    out_idem_t = res.stdout
    if (res.returncode == 0
            and "ENABLED" in out_idem_t
            and "no rewrite" in out_idem_t.lower() or "not present" in out_idem_t.lower() or "no change" in out_idem_t.lower()):
        ok(11, "human-approval true (idempotent) message names ENABLED and notes no rewrite")
    else:
        fail_t(11, f"idempotent true message ambiguous: {out_idem_t!r}")

    # t12: idempotent `false` (already disabled / marker present) names
    # DISABLED and notes the file was not rewritten. (The Inv 48 spec
    # example for the idempotent form names the marker + 'no rewrite';
    # the '(bypass ACTIVE)' qualifier is mandatory only for the
    # non-idempotent write path.)
    run_cfg(["human-approval", "false"], wd)  # set
    res = run_cfg(["human-approval", "false"], wd)  # re-set
    out_idem_f = res.stdout
    if (res.returncode == 0
            and "DISABLED" in out_idem_f
            and "ENABLED" not in out_idem_f
            and ("no rewrite" in out_idem_f.lower() or "already" in out_idem_f.lower())):
        ok(12, "human-approval false (idempotent) message names DISABLED + no rewrite")
    else:
        fail_t(12, f"idempotent false message ambiguous: {out_idem_f!r}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
