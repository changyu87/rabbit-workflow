#!/usr/bin/env python3
"""rabbit-cage Inv 35 — /rabbit-update command (check + install).

Covers issue #493: a user-invocable /rabbit-update slash command routing
two DETERMINISTIC subcommands to a companion script:

  - `check`   — non-mutating; reports current vs latest release.
  - `install` — applies the self-update via install.py --update.

Assertions (mix of unit + e2e):
  t1  scripts/rabbit-update.py exists and is executable.
  t2  `rabbit-update.py check` (release source injected) prints a structured
      current-vs-latest JSON result (current/latest/newer keys).
  t3  `check` is non-mutating: it does NOT write the throttle file
      (forces a fresh probe regardless of the SessionStart throttle).
  t4  `rabbit-update.py install` invokes the install.py --update self-update
      path (asserts the install.py entry + --update flag; no network call).
  t5  commands/rabbit-update.md has required frontmatter
      (version/owner/deprecation_criterion).
  t6  the command body invokes the companion script (no model-assembled
      bash with runtime placeholders — the script owns the logic).
  t7  feature.json manifest registers publish_command for
      commands/rabbit-update.md.
  t8  FEATURE_INCLUDES["rabbit-cage"] lists both the command md and the
      backing script (Inv 21 manifest-source + Inv 24 script closure).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
UPDATE_PY = os.path.join(CAGE_DIR, "scripts/rabbit-update.py")
UPDATE_MD = os.path.join(CAGE_DIR, "commands/rabbit-update.md")
FEATURE_JSON = os.path.join(CAGE_DIR, "feature.json")
INSTALL_PY = os.path.join(CAGE_DIR, "install.py")

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


print("test-rabbit-update-command.py")

# t1 — script exists and is executable
if os.path.isfile(UPDATE_PY) and os.access(UPDATE_PY, os.X_OK):
    ok(1, "scripts/rabbit-update.py exists and is executable")
else:
    fail_t(1, "scripts/rabbit-update.py missing or not executable")


def _make_fake_root(tmp, current):
    """Build a minimal rabbit root with .version, a copy of the real
    check-release-update.py, and a stub install.py carrying the self-update
    marker."""
    os.makedirs(os.path.join(tmp, ".claude/features/contract/scripts"),
                exist_ok=True)
    with open(os.path.join(tmp, ".version"), "w") as f:
        f.write(current)
    src = os.path.join(
        REPO_ROOT,
        ".claude/features/contract/scripts/check-release-update.py")
    shutil.copy2(src, os.path.join(
        tmp, ".claude/features/contract/scripts/check-release-update.py"))
    with open(os.path.join(tmp, "install.py"), "w") as f:
        f.write("# fetch_upstream marker\n")
    return tmp


# t2 + t3 — `check` returns structured current-vs-latest, non-mutating
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp, "v1.0.0")
    env = os.environ.copy()
    env["RABBIT_ROOT"] = tmp
    # Inject the latest-release value so no network call happens.
    env["RABBIT_UPDATE_TEST_LATEST"] = "v1.2.0"
    res = subprocess.run(
        [sys.executable, UPDATE_PY, "check"],
        capture_output=True, text=True, env=env,
    )
    raw = (res.stdout or "").strip()
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if (res.returncode == 0 and isinstance(parsed, dict)
            and parsed.get("current") == "v1.0.0"
            and parsed.get("latest") == "v1.2.0"
            and parsed.get("newer") is True):
        ok(2, "`check` prints structured current-vs-latest JSON (newer=true)")
    else:
        fail_t(2, f"`check` output unexpected: rc={res.returncode} "
                  f"stdout={raw!r} stderr={res.stderr.strip()!r}")

    throttle = os.path.join(tmp, ".rabbit", ".runtime", "last-update-check")
    if not os.path.isfile(throttle):
        ok(3, "`check` is non-mutating (no throttle file written)")
    else:
        fail_t(3, "`check` wrote the throttle file — must force a fresh probe")

# t4 — `install` invokes install.py --update (no real network install)
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp, "v1.0.0")
    recorder = os.path.join(tmp, "install.py")
    log = os.path.join(tmp, "install-invocation.log")
    with open(recorder, "w") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "# fetch_upstream marker\n"
            f"open({log!r}, 'w').write(' '.join(sys.argv[1:]))\n"
            "sys.exit(0)\n"
        )
    os.chmod(recorder, 0o755)
    env = os.environ.copy()
    env["RABBIT_ROOT"] = tmp
    res = subprocess.run(
        [sys.executable, UPDATE_PY, "install"],
        capture_output=True, text=True, env=env,
    )
    logged = ""
    if os.path.isfile(log):
        with open(log) as f:
            logged = f.read()
    if res.returncode == 0 and "--update" in logged:
        ok(4, "`install` invokes install.py with --update")
    else:
        fail_t(4, f"`install` did not invoke install.py --update: "
                  f"rc={res.returncode} logged={logged!r} "
                  f"stderr={res.stderr.strip()!r}")

# t5 — command frontmatter
if os.path.isfile(UPDATE_MD):
    md = open(UPDATE_MD).read()
    fm = re.search(r"(?ms)^---\s*\n(.*?)\n---\s*\n", md)
    if fm:
        block = fm.group(1)
        has_v = re.search(r"(?m)^version:\s*\S+", block)
        has_o = re.search(r"(?m)^owner:\s*\S+", block)
        has_d = re.search(r"(?m)^deprecation_criterion:\s*\S+", block)
        if has_v and has_o and has_d:
            ok(5, "rabbit-update.md has version/owner/deprecation_criterion")
        else:
            fail_t(5, "rabbit-update.md frontmatter missing required field(s)")
    else:
        fail_t(5, "rabbit-update.md has no YAML frontmatter")
else:
    fail_t(5, "commands/rabbit-update.md missing")

# t6 — body invokes the companion script
if os.path.isfile(UPDATE_MD):
    md = open(UPDATE_MD).read()
    if "scripts/rabbit-update.py" in md:
        ok(6, "command body invokes scripts/rabbit-update.py")
    else:
        fail_t(6, "command body does not reference scripts/rabbit-update.py")
else:
    fail_t(6, "commands/rabbit-update.md missing")

# t7 — manifest registers the command
data = json.loads(open(FEATURE_JSON).read())
manifest = data.get("manifest") or []
registered = any(
    e.get("api") == "publish_command"
    and (e.get("args") or {}).get("source") == "commands/rabbit-update.md"
    for e in manifest
)
if registered:
    ok(7, "feature.json manifest registers commands/rabbit-update.md")
else:
    fail_t(7, "feature.json manifest does not register rabbit-update.md")

# t8 — FEATURE_INCLUDES closure
spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
includes = getattr(mod, "FEATURE_INCLUDES", {}).get("rabbit-cage", [])
need = ["commands/rabbit-update.md", "scripts/rabbit-update.py"]
missing = [p for p in need if p not in includes]
if not missing:
    ok(8, "FEATURE_INCLUDES[rabbit-cage] lists command + script")
else:
    fail_t(8, f"FEATURE_INCLUDES[rabbit-cage] missing: {missing}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
