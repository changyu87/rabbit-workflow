#!/usr/bin/env python3
"""End-to-end tests for rabbit-cage Wave 3 (Inv 66-68).

Inv 66: new-feature.py scaffolds test/run.py (not test/run.sh), feature.json
        contains template_version, and the scaffolded feature passes
        validate-feature.py immediately.
Inv 67: commands/rabbit-project.md references only existing .py scripts;
        no `.sh` references; any referenced script path actually exists.
Inv 68: rabbit-config.py human-approval messages name both the marker state
        and the practical effect (BYPASSED / ENABLED + Step 4 verbiage), and
        do not use the bare ambiguous adjective `DISABLED`.
"""
import json
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

NEW_FEATURE_PY = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/scripts/new-feature.py"
)
RABBIT_PROJECT_MD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/commands/rabbit-project.md"
)
RABBIT_CONFIG_PY = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py",
)
VALIDATE_FEATURE_PY = os.path.join(
    REPO_ROOT, ".claude/features/contract/scripts/validate-feature.py"
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
# Inv 66: new-feature.py scaffolds test/run.py + template_version
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory(prefix="rc-wave3-") as tmp:
    # Pretend RABBIT_ROOT points at the real repo so the optional
    # validate-feature.py self-check can find the script.
    env = dict(os.environ)
    env["RABBIT_ROOT"] = REPO_ROOT

    res = subprocess.run(
        [sys.executable, NEW_FEATURE_PY, tmp, "wave3-demo",
         "--owner", "rc-test", "--description", "wave3 e2e"],
        env=env, capture_output=True, text=True,
    )
    if res.returncode != 0:
        fail_t(1, f"new-feature.py exited {res.returncode}; stderr={res.stderr!r}")
    else:
        ok(1, "new-feature.py scaffolds successfully")

    feature_dir = os.path.join(tmp, "wave3-demo")
    run_py = os.path.join(feature_dir, "test", "run.py")
    run_sh = os.path.join(feature_dir, "test", "run.sh")

    # t2: test/run.py exists.
    if os.path.isfile(run_py):
        ok(2, "scaffold creates test/run.py")
    else:
        fail_t(2, "scaffold missing test/run.py")

    # t3: test/run.sh must NOT be scaffolded (Python-only stack per Inv 39).
    if not os.path.lexists(run_sh):
        ok(3, "scaffold does NOT create test/run.sh (Python-only per Inv 39)")
    else:
        fail_t(3, "scaffold still creates test/run.sh (violates Inv 39/66)")

    # t4: test/run.py is executable.
    if os.path.isfile(run_py) and os.access(run_py, os.X_OK):
        ok(4, "scaffolded test/run.py is executable")
    else:
        fail_t(4, "scaffolded test/run.py is not executable")

    # t5: feature.json contains template_version.
    fjson = os.path.join(feature_dir, "feature.json")
    if os.path.isfile(fjson):
        try:
            with open(fjson) as f:
                data = json.load(f)
            if data.get("template_version"):
                ok(5, f"feature.json carries template_version={data['template_version']!r}")
            else:
                fail_t(5, "feature.json missing template_version field")
        except Exception as e:
            fail_t(5, f"feature.json could not be parsed: {e}")
    else:
        fail_t(5, "feature.json was not scaffolded")

    # t6: validate-feature.py passes on the freshly scaffolded feature.
    if os.path.isfile(VALIDATE_FEATURE_PY):
        vres = subprocess.run(
            [sys.executable, VALIDATE_FEATURE_PY, feature_dir],
            capture_output=True, text=True,
        )
        if vres.returncode == 0:
            ok(6, "scaffolded feature passes validate-feature.py immediately")
        else:
            fail_t(6, f"validate-feature.py rc={vres.returncode}; stderr={vres.stderr!r}")
    else:
        fail_t(6, f"validate-feature.py not found at {VALIDATE_FEATURE_PY}")

# ---------------------------------------------------------------------------
# Inv 67: commands/rabbit-project.md references only existing .py scripts
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
# Inv 68: rabbit-config.py human-approval messages
# ---------------------------------------------------------------------------
def run_cfg(args, wd):
    return subprocess.run(
        [sys.executable, RABBIT_CONFIG_PY] + list(args),
        cwd=wd, capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory(prefix="rc-wave3-cfg-") as wd:
    # t9: `false` message names BYPASSED + marker name + Step 4 effect.
    res = run_cfg(["human-approval", "false"], wd)
    out = res.stdout
    needed_false = ["BYPASSED", ".rabbit-human-approval-bypass", "Step 4"]
    missing_false = [s for s in needed_false if s not in out]
    if res.returncode == 0 and not missing_false:
        ok(9, "human-approval false message names BYPASSED + marker + Step 4")
    else:
        fail_t(9, f"missing {missing_false!r} in stdout={out!r}")

    # t10: `false` message must NOT use the bare adjective DISABLED.
    if "DISABLED" not in out:
        ok(10, "human-approval false message avoids ambiguous 'DISABLED'")
    else:
        fail_t(10, f"human-approval false still says 'DISABLED' in: {out!r}")

    # t11: `true` message names ENABLED + marker removal + Step 4 effect.
    res = run_cfg(["human-approval", "true"], wd)
    out_true = res.stdout
    needed_true = ["ENABLED", ".rabbit-human-approval-bypass", "Step 4"]
    missing_true = [s for s in needed_true if s not in out_true]
    if res.returncode == 0 and not missing_true:
        ok(11, "human-approval true message names ENABLED + marker + Step 4")
    else:
        fail_t(11, f"missing {missing_true!r} in stdout={out_true!r}")

    # t12: idempotent `true` (already enabled) message still names ENABLED.
    res = run_cfg(["human-approval", "true"], wd)
    out_idem = res.stdout
    if res.returncode == 0 and "ENABLED" in out_idem and "DISABLED" not in out_idem:
        ok(12, "human-approval true (idempotent) message names ENABLED")
    else:
        fail_t(12, f"idempotent true message ambiguous: {out_idem!r}")

    # t13: idempotent `false` (already bypassed) message still names BYPASSED.
    run_cfg(["human-approval", "false"], wd)  # set
    res = run_cfg(["human-approval", "false"], wd)  # re-set
    out_idem_f = res.stdout
    if (res.returncode == 0
            and "BYPASSED" in out_idem_f
            and "DISABLED" not in out_idem_f):
        ok(13, "human-approval false (idempotent) message names BYPASSED")
    else:
        fail_t(13, f"idempotent false message ambiguous: {out_idem_f!r}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
