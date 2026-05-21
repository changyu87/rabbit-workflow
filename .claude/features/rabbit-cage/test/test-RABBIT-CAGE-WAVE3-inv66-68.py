#!/usr/bin/env python3
"""End-to-end tests for rabbit-cage Wave 3 (Inv 47-48).

Inv 47: commands/rabbit-project.md references only existing .py scripts;
        no `.sh` references; any referenced script path actually exists.
Inv 48 (post-BACKLOG-31): rabbit-config.py bypass-human-approval messages name the marker state
        and the practical effect (BYPASSED / ENABLED + Step 4 verbiage), and
        do not use the bare ambiguous adjective `DISABLED`.

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
# Inv 48 (post-BACKLOG-31 rename): rabbit-config.py bypass-human-approval messages.
# Subcommand renamed to bypass-human-approval with inverted boolean semantics
# parallel to bypass-permissions: true = bypass ENABLED (marker written);
# false = bypass DISABLED (marker removed). Confirmation text follows the
# ENABLED/DISABLED pattern (no more 'BYPASSED'/'ENABLED' gate framing).
# ---------------------------------------------------------------------------
def run_cfg(args, wd):
    return subprocess.run(
        [sys.executable, RABBIT_CONFIG_PY] + list(args),
        cwd=wd, capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory(prefix="rc-wave3-cfg-") as wd:
    # t9: `true` message names ENABLED + marker name + Step 4 effect.
    res = run_cfg(["bypass-human-approval", "true"], wd)
    out = res.stdout
    needed_true = ["ENABLED", ".rabbit-human-approval-bypass", "Step 4"]
    missing_true = [s for s in needed_true if s not in out]
    if res.returncode == 0 and not missing_true:
        ok(9, "bypass-human-approval true message names ENABLED + marker + Step 4")
    else:
        fail_t(9, f"missing {missing_true!r} in stdout={out!r}")

    # t10: `true` message must NOT use the legacy 'BYPASSED' framing.
    if "BYPASSED" not in out:
        ok(10, "bypass-human-approval true message avoids legacy 'BYPASSED' framing")
    else:
        fail_t(10, f"bypass-human-approval true still says 'BYPASSED' in: {out!r}")

    # t11: `false` message names DISABLED + marker removal + Step 4 effect.
    res = run_cfg(["bypass-human-approval", "false"], wd)
    out_false = res.stdout
    needed_false = ["DISABLED", ".rabbit-human-approval-bypass", "Step 4"]
    missing_false = [s for s in needed_false if s not in out_false]
    if res.returncode == 0 and not missing_false:
        ok(11, "bypass-human-approval false message names DISABLED + marker + Step 4")
    else:
        fail_t(11, f"missing {missing_false!r} in stdout={out_false!r}")

    # t12: idempotent `false` (already disabled) message still names DISABLED.
    res = run_cfg(["bypass-human-approval", "false"], wd)
    out_idem = res.stdout
    if res.returncode == 0 and "DISABLED" in out_idem and "ENABLED" not in out_idem:
        ok(12, "bypass-human-approval false (idempotent) message names DISABLED")
    else:
        fail_t(12, f"idempotent false message ambiguous: {out_idem!r}")

    # t13: idempotent `true` (already enabled) message still names ENABLED.
    run_cfg(["bypass-human-approval", "true"], wd)  # set
    res = run_cfg(["bypass-human-approval", "true"], wd)  # re-set
    out_idem_t = res.stdout
    if (res.returncode == 0
            and "ENABLED" in out_idem_t
            and "BYPASSED" not in out_idem_t):
        ok(13, "bypass-human-approval true (idempotent) message names ENABLED")
    else:
        fail_t(13, f"idempotent true message ambiguous: {out_idem_t!r}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
