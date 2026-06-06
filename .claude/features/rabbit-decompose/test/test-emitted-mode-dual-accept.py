#!/usr/bin/env python3
"""test-emitted-mode-dual-accept.py — the EMITTED mode field survives the
vendored rename (Invariant 10 emitted-field clause).

The #988 prep dual-accepted `handoff-scaffold.py`'s INTERNAL branch
comparisons (`mode in ("vendored", "plugin")`), so the script routes a
`"vendored"`-mode run down the vendored path. But `handoff-scaffold.py` emits
the resolved `detect_mode()` value VERBATIM into its output `mode` field, and
the feature's own E2E suite STRICTLY asserted that emitted field == `"plugin"`
at several sites. The moment `detect_mode` flips its vendored value from
`"plugin"` to `"vendored"` (the coordinated rename, owned by rabbit-meta),
those strict assertions would RED — they are the last consumers blocking the
flip.

This guard simulates that flip DETERMINISTICALLY and end-to-end, WITHOUT
touching the rabbit-meta detector: it stands up a temp `.claude/features/`
tree containing a COPY of this feature's `scripts/handoff-scaffold.py` and a
FAKE `rabbit-meta/lib/mode_detection.py` whose `detect_mode` returns
`"vendored"` for a vendored signature (instead of `"plugin"`). Because
`handoff-scaffold.py` resolves the detector by walking UP to the nearest
`.claude/features/rabbit-meta/lib/mode_detection.py`, the copied script binds
to the fake. It then drives the three emitted-`mode` consumers
(`--source-root`, `--plan-only`, `--detect-existing`) and asserts:

  1. each emits the post-rename `mode` value `"vendored"` (the flip is live in
     this temp tree);
  2. the vendored BEHAVIOUR is preserved — `--plan-only` still takes the batch
     branch, `--source-root` is still parent-of-`.rabbit`, `--detect-existing`
     still reads the vendored-location project-map; and
  3. the feature's own emitted-mode test assertions DUAL-ACCEPT this value:
     the guard greps the suite for any strict emitted-`mode == "plugin"` /
     `!= "plugin"` field assertion that is NOT a dual-accept and FAILS if one
     remains, so a future detect_mode flip leaves `test/run.py` fully green.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: removed when the #980 migration completes and the
    legacy "plugin" value is fully retired, leaving only "vendored" — at which
    point the emitted-mode assertions check "vendored" alone.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")
TEST_DIR = os.path.join(FEATURE_DIR, "test")

# A fake rabbit-meta detector that returns the POST-RENAME vendored value.
# Same structural signature as the real detector (basename == ".rabbit" with a
# non-.rabbit host sibling), but emits "vendored" where the real one currently
# emits "plugin".
FAKE_MODE_DETECTION = '''\
import os


def detect_mode(cwd):
    try:
        entries = os.listdir(os.path.dirname(cwd))
    except OSError:
        return "standalone"
    if os.path.basename(cwd) == ".rabbit" and any(n != ".rabbit" for n in entries):
        return "vendored"
    return "standalone"
'''


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


if not os.path.isfile(SCRIPT):
    fail(f"missing handoff-scaffold.py: {SCRIPT}")


def _make_flipped_tree(parent):
    """A `.claude/features/` tree under `parent` with a COPY of this feature's
    handoff-scaffold.py and a FAKE rabbit-meta detector returning "vendored".

    Returns (script_copy_path, rabbit_root, host) where host is the user
    project (parent of .rabbit) and rabbit_root is the .rabbit install."""
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    feat_root = os.path.join(rabbit_root, ".claude", "features")
    # decompose copy
    dec_scripts = os.path.join(feat_root, "rabbit-decompose", "scripts")
    os.makedirs(dec_scripts)
    script_copy = os.path.join(dec_scripts, "handoff-scaffold.py")
    shutil.copyfile(SCRIPT, script_copy)
    # fake rabbit-meta detector (returns "vendored")
    meta_lib = os.path.join(feat_root, "rabbit-meta", "lib")
    os.makedirs(meta_lib)
    with open(os.path.join(meta_lib, "mode_detection.py"), "w",
              encoding="utf-8") as f:
        f.write(FAKE_MODE_DETECTION)
    return script_copy, rabbit_root, host


def _run(script, args, workdir):
    proc = subprocess.run(
        [sys.executable, script, *args],
        capture_output=True, text=True, cwd=workdir,
    )
    if proc.returncode != 0:
        fail(f"{os.path.basename(script)} {args} exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"{args} did not emit JSON: {e}; stdout:\n{proc.stdout}")


# --- Checks 1-2: with detect_mode -> "vendored", the emitted field is
#                 "vendored" AND the vendored behaviour is preserved ----------
with tempfile.TemporaryDirectory() as td:
    script, rabbit_root, host = _make_flipped_tree(td)

    # --source-root: emitted mode == "vendored"; source_root == parent-of-.rabbit
    res = _run(script, ["--source-root", "--rabbit-root", rabbit_root], host)
    if res.get("mode") != "vendored":
        fail("post-rename --source-root must emit mode 'vendored' (the flipped "
             f"detect_mode value), got {res.get('mode')!r}")
    if os.path.realpath(res.get("source_root") or "") != os.path.realpath(host):
        fail("post-rename --source-root must still resolve parent-of-.rabbit "
             f"({host!r}), got {res.get('source_root')!r}")

    # --plan-only: emitted mode == "vendored"; STILL the batch branch
    feats = os.path.join(td, "accepted.json")
    with open(feats, "w", encoding="utf-8") as f:
        json.dump([{"name": "f-one", "globs": ["a/**"]}], f)
    plan = _run(script, ["--features", feats, "--rabbit-root", rabbit_root,
                         "--plan-only"], host)
    if plan.get("mode") != "vendored":
        fail("post-rename --plan-only must emit mode 'vendored', got "
             f"{plan.get('mode')!r}")
    if plan.get("branch") != "batch":
        fail("post-rename --plan-only must STILL take the batch (vendored) "
             f"branch, got branch={plan.get('branch')!r}")

    # --detect-existing: emitted mode == "vendored"; reads the vendored-location
    # project-map (<rabbit_root>/rabbit-project/project-map.json)
    pmap_dir = os.path.join(rabbit_root, "rabbit-project")
    os.makedirs(pmap_dir)
    with open(os.path.join(pmap_dir, "project-map.json"), "w",
              encoding="utf-8") as f:
        json.dump({"schema_version": "1.0.0",
                   "features": {"alpha": {"paths": ["src/**"]}}}, f)
    det = _run(script, ["--detect-existing", "--rabbit-root", rabbit_root],
               host)
    if det.get("mode") != "vendored":
        fail("post-rename --detect-existing must emit mode 'vendored', got "
             f"{det.get('mode')!r}")
    if det.get("existing") is not True:
        fail("post-rename --detect-existing must STILL read the vendored-location "
             "project-map (existing=True), got "
             f"existing={det.get('existing')!r}")


# --- Check 3: no strict emitted-mode `== "plugin"` assertion remains in the
#              suite (every such field check must dual-accept) -----------------
# Match a comparison of the EMITTED mode field against the bare "plugin" value:
#   res.get("mode") != "plugin"   |   plan.get("mode") == "plugin"
#   x["mode"] != "plugin"         |   etc.
# A dual-accept site reads `not in ("vendored", "plugin")` / `in (...)` and is
# NOT matched here. The `!= "standalone"` arm of a toggle check is fine (it
# proves the toggle); only the "plugin"-value arm must be relaxed.
_STRICT = re.compile(
    r'(?:\.get\(\s*["\']mode["\']\s*\)|\[\s*["\']mode["\']\s*\])'
    r'\s*(?:==|!=)\s*["\']plugin["\']'
)

offenders = []
for name in sorted(os.listdir(TEST_DIR)):
    if not (name.startswith("test-") and name.endswith(".py")):
        continue
    if name == os.path.basename(__file__):
        continue
    path = os.path.join(TEST_DIR, name)
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if _STRICT.search(line):
                offenders.append(f"{name}:{lineno}: {line.strip()}")

if offenders:
    fail("strict emitted-mode `== \"plugin\"` field assertion(s) remain — they "
         "would RED when detect_mode flips to \"vendored\"; each must "
         "dual-accept `mode in/not in (\"vendored\", \"plugin\")`:\n  "
         + "\n  ".join(offenders))

print("All checks passed.")
