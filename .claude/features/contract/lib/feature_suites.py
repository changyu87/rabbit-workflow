"""contract.lib.feature_suites — discover and run every feature's own test suite.

The contract repo-gate (test/run.py) runs cross-feature contract checks. These
helpers add the missing dimension: discovering every feature's own
`.claude/features/<name>/test/run.py` and running each, so a change in feature
A that REDS feature B's per-feature suite is caught at the repo-gate (per
spec Inv 66).

`contract` is EXCLUDED from discovery so the gate never re-invokes its own
test/run.py (no infinite recursion); contract's own suite is the runner that
invokes this check. `policy` and any other non-suite directory (no
`test/run.py`) is skipped silently.

Runtime: running every feature suite on every gate is not free. The default is
to run them all (the gate must catch the regression). For fast local iteration
the `RABBIT_SKIP_PER_FEATURE_SUITES` env var, when set to a truthy value,
makes `run_feature_suites` return an empty result without running anything —
this is a local-only escape hatch and is never set in the CI/repo gate.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when a native rabbit CLI exposes equivalent bindings.
"""

import os
import subprocess
import sys

# Features that own no per-feature suite, or whose suite would recurse into
# the very runner invoking this check. `contract` is the runner itself.
_EXCLUDED_FEATURES = {"contract"}

_SKIP_ENV = "RABBIT_SKIP_PER_FEATURE_SUITES"


def discover_feature_suites(features_root):
    """Return a deterministic, name-sorted list of (feature_name, run_py_path)
    for every feature under `features_root` that owns a `test/run.py`.

    Excludes `contract` (the runner itself) and any dir without `test/run.py`.
    """
    suites = []
    if not os.path.isdir(features_root):
        return suites
    for name in sorted(os.listdir(features_root)):
        if name.startswith("."):
            continue
        if name in _EXCLUDED_FEATURES:
            continue
        fdir = os.path.join(features_root, name)
        if not os.path.isdir(fdir):
            continue
        run_py = os.path.join(fdir, "test", "run.py")
        if os.path.isfile(run_py):
            suites.append((name, run_py))
    return suites


def run_feature_suites(features_root, *, timeout=None):
    """Run every discovered per-feature suite under `features_root`.

    Returns a name-sorted list of (feature_name, passed, output) tuples, where
    `passed` is True iff that feature's `test/run.py` exited 0 and `output` is
    its combined stdout+stderr. A non-zero exit (including timeout) is `passed
    is False`.

    Honours the `RABBIT_SKIP_PER_FEATURE_SUITES` local escape hatch: when set
    truthy, returns an empty list without running anything.
    """
    if os.environ.get(_SKIP_ENV):
        return []
    results = []
    for name, run_py in discover_feature_suites(features_root):
        try:
            proc = subprocess.run(
                [sys.executable, run_py],
                capture_output=True, text=True, timeout=timeout,
            )
            passed = proc.returncode == 0
            output = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            passed = False
            output = f"TIMEOUT after {exc.timeout}s running {run_py}"
        results.append((name, passed, output))
    return results
