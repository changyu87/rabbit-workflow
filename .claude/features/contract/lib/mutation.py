"""contract.lib.mutation — API library for state-mutation primitives used by
the rabbit-config dispatcher when a feature's CONFIGURATION declares a value
change.

Each function implements one mutation API call as declared in a feature's
CONFIGURATION section. Functions accept their declared args plus keyword-only
context params (repo_root for filesystem APIs; feature_dir for the script
escape hatch) and return CheckResult.

All mutations are idempotent: re-running with unchanged effective state
returns a CheckResult whose messages contain "no-op". (The
`run_feature_script` escape hatch delegates idempotency to the invoked
script.)

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native configuration mutation.
"""

import json
import os
import subprocess

from lib.checks import CheckResult


def write_marker(path: str, content: str, *, repo_root: str) -> CheckResult:
    """Write a marker file at path (repo-root-relative) with given content.

    Idempotent: if the marker already exists with identical content, returns
    passed=True with a 'no-op' message and does not touch the file.
    Parent directories are created automatically.
    """
    dst = os.path.join(repo_root, path)
    if os.path.isfile(dst):
        try:
            with open(dst) as f:
                if f.read() == content:
                    return CheckResult(True, [f"OK: {path} unchanged (no-op)"])
        except OSError:
            pass
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dst, "w") as f:
        f.write(content)
    return CheckResult(True, [f"OK: {path} written"])
