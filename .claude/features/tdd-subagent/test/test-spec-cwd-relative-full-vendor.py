#!/usr/bin/env python3
"""Inv 63 — `--spec` resolution is full-vendor-safe (cwd-relative).

#1085 Strategy D acceptance criterion (the convergence step): no
tdd-subagent dispatch-contract change is required for the full-vendor
worktree cycle, because `dispatch-tdd-subagent.py` resolves `--spec`
relative to the process CURRENT WORKING DIRECTORY. When the cycle invokes
the dispatcher from inside a self-contained vendored worktree (where the
whole `.rabbit/` is tracked, #1086, and the cycle runs from
`<worktree>/.rabbit`, #1087), the spec lives at the SAME relative path it
occupies in standalone mode — so cwd-relative resolution finds it without
any path-rewriting on the dispatch boundary.

This is an END-TO-END test. It builds two real on-disk layouts and runs
the live `dispatch-tdd-subagent.py` in a subprocess whose cwd is the
operating root, passing `--spec` as a CWD-RELATIVE path:

  A) STANDALONE layout — repo root carries `.claude/features/<x>/`; the
     dispatcher is run with cwd = repo root and a CWD-RELATIVE `--spec`.
  B) FULL-VENDOR self-contained worktree layout — a worktree dir whose
     `.rabbit/` is the self-contained checkout (tool + work co-located);
     the cycle's cwd is `<worktree>/.rabbit` (which IS RABBIT_ROOT), the
     user-project feature spec lives at
     `.rabbit/rabbit-project/features/<x>/docs/spec.md`, and `--spec` is
     passed RELATIVE to that cwd. The dispatcher MUST find the spec and
     embed it.

Both assert the resolved spec body is embedded in the assembled prompt,
proving cwd-relative `--spec` resolution works identically in both
layouts — the property #1085's "no contract change" criterion depends on.
The per-mode feature ROOT differs (standalone scans `.claude/features/`,
vendored adds `rabbit-project/features/`), but the `--spec` RESOLUTION
mechanism is the same cwd-relative path lookup in both.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from _helpers import DISPATCH_PY, REPO_ROOT, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _populate_root(root):
    """Copy the live contract/tdd-subagent/policy feature trees into `root`
    so find-feature.py + build-prompt.py + templates + injected policy are
    all present at the canonical relative locations."""
    src_features = os.path.join(REPO_ROOT, ".claude", "features")
    dst_features = os.path.join(root, ".claude", "features")
    for feat in ("contract", "tdd-subagent", "policy"):
        src = os.path.join(src_features, feat)
        dst = os.path.join(dst_features, feat)
        if os.path.isdir(src):
            shutil.copytree(src, dst)


SPEC_BODY = "# probe-feature spec\n\nUNIQUE_PROBE_MARKER_42\n"
FEATURE_JSON = (
    '{"name": "probe-feature", "version": "0.1.0", "owner": "x", '
    '"summary": "x", "surface": {"hooks": [], "commands": [], '
    '"skills": []}, "tdd_state": "spec"}'
)
# Vendored feature root is `rabbit-project/features/`; standalone is
# `.claude/features/`. Each is the canonical scan location for its mode.
REL_SPEC_VENDORED = os.path.join("rabbit-project", "features", "probe-feature",
                                 "docs", "spec.md")
REL_SPEC_STANDALONE = os.path.join(".claude", "features", "probe-feature",
                                   "docs", "spec.md")


# ---------------------------------------------------------------------------
# Scenario A: STANDALONE — cwd = repo root, --spec is cwd-relative.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, "standalone")
    os.makedirs(root)
    _populate_root(root)
    feat_dir = os.path.join(root, ".claude", "features", "probe-feature")
    _write(os.path.join(feat_dir, "feature.json"), FEATURE_JSON)
    _write(os.path.join(feat_dir, "docs", "spec.md"), SPEC_BODY)

    env = os.environ.copy()
    env.pop("RABBIT_ROOT", None)
    # Standalone resolves repo root via cwd-based git rev-parse, so make the
    # operating root a git toplevel.
    subprocess.run(["git", "init", "-q", root], check=True)
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "probe-feature",
         "--spec", REL_SPEC_STANDALONE],
        capture_output=True, text=True, env=env, cwd=root,
    )
    if res.returncode == 0 and "UNIQUE_PROBE_MARKER_42" in res.stdout:
        ok("standalone: cwd-relative --spec resolves and spec body is embedded")
    else:
        ko(f"standalone: expected rc=0 + spec embedded, got rc={res.returncode}, "
           f"stderr={res.stderr!r}")


# ---------------------------------------------------------------------------
# Scenario B: FULL-VENDOR self-contained worktree — cwd = <worktree>/.rabbit
# (== RABBIT_ROOT), --spec is the canonical vendored cwd-relative spec path.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    # Simulate a vendored worktree: a host worktree dir whose self-contained
    # `.rabbit/` is the tracked tool+work checkout (#1086/#1087). The cycle
    # runs from <worktree>/.rabbit, which IS RABBIT_ROOT (Inv 47).
    worktree = os.path.join(tmp, "worktree")
    rabbit_root = os.path.join(worktree, ".rabbit")
    os.makedirs(rabbit_root)
    _populate_root(rabbit_root)
    # Vendored mode marker so mode-aware path emission selects vendored.
    _write(os.path.join(rabbit_root, ".runtime", "mode"), "vendored")
    feat_dir = os.path.join(rabbit_root, "rabbit-project", "features",
                            "probe-feature")
    _write(os.path.join(feat_dir, "feature.json"), FEATURE_JSON)
    # The spec lives at the canonical vendored scan location inside .rabbit/.
    _write(os.path.join(feat_dir, "docs", "spec.md"), SPEC_BODY)

    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root
    # cwd is <worktree>/.rabbit and --spec is the canonical cwd-relative spec
    # path inside the self-contained tree — proving no contract change is
    # needed on the dispatch boundary.
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "probe-feature",
         "--spec", REL_SPEC_VENDORED],
        capture_output=True, text=True, env=env, cwd=rabbit_root,
    )
    if res.returncode == 0 and "UNIQUE_PROBE_MARKER_42" in res.stdout:
        ok("full-vendor worktree: cwd-relative --spec resolves and "
           "spec body is embedded (no contract change needed)")
    else:
        ko(f"full-vendor worktree: expected rc=0 + spec embedded, got "
           f"rc={res.returncode}, stderr={res.stderr!r}")


report(passed, failed)
