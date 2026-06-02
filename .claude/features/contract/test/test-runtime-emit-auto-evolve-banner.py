#!/usr/bin/env python3
"""test-runtime-emit-auto-evolve-banner.py — exercises emit_auto_evolve_banner
per Inv 65 (v1.51.1 dispatch refactor).

emit_auto_evolve_banner delegates line-1 and line-2 content to
rabbit-auto-evolve/scripts/banner-status.py via subprocess. Contract owns the
dispatch mechanism (gate marker check, script-path resolution, subprocess
invocation, JSON parse, mapping to print_result entries); rabbit-auto-evolve
owns the content (the per-variant line-1/line-2 text/icon/color).

This test mocks banner-status.py with throwaway scripts written into a tempdir
layout matching .claude/features/rabbit-auto-evolve/scripts/banner-status.py
and verifies the contract-side dispatch behavior across the failure modes.

Per-variant content (default vs running vs restart-needed vs aborted) is
exercised by rabbit-auto-evolve's own test-banner-status.py (Inv 22 in
rabbit-auto-evolve). This test only verifies dispatch + mapping.
"""

import json
import os
import stat
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_auto_evolve_banner  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def touch(root, name, content=""):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


SCRIPT_REL = ".claude/features/rabbit-auto-evolve/scripts/banner-status.py"


def write_mock_script(td, body):
    """Create the mock banner-status.py at the conventional path."""
    path = os.path.join(td, SCRIPT_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def emit_json_script(payload):
    """Build a mock script body that prints the given JSON payload and exits 0."""
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({json.dumps(json.dumps(payload))})\n"
        "sys.exit(0)\n"
    )


# A: no .rabbit-auto-evolve-active marker -> [] (gate; script not invoked)
with tempfile.TemporaryDirectory() as td:
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("A: marker absent returns []")
    else:
        fail(f"A: expected [], got {r!r}")


# B: marker present + script returns active:true with line1+line2 -> 2 entries
#    propagated verbatim from JSON
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_mock_script(td, emit_json_script({
        "active": True,
        "line1": {"text": "L1-TEXT", "icon": "X", "color": "red"},
        "line2": {"text": "L2-TEXT", "icon": "Y", "color": "yellow"},
    }))
    r = emit_auto_evolve_banner(repo_root=td)
    expected = [
        {"type": "print", "text": "L1-TEXT", "icon": "X", "color": "red"},
        {"type": "print", "text": "L2-TEXT", "icon": "Y", "color": "yellow"},
    ]
    if r == expected:
        ok("B: marker + active:true script -> 2 print_result entries propagated verbatim")
    else:
        fail(f"B: expected {expected!r}, got {r!r}")


# C: marker present + script missing -> []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    # do not write the mock script
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("C: marker + script missing returns []")
    else:
        fail(f"C: expected [], got {r!r}")


# D: marker present + script exits non-zero -> []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_mock_script(td, (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.exit(1)\n"
    ))
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("D: marker + script exits non-zero returns []")
    else:
        fail(f"D: expected [], got {r!r}")


# E: marker present + script emits malformed JSON -> []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_mock_script(td, (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.write('not-json{{{')\n"
        "sys.exit(0)\n"
    ))
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("E: marker + script malformed JSON returns []")
    else:
        fail(f"E: expected [], got {r!r}")


# F: marker present + script returns active:false -> []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_mock_script(td, emit_json_script({"active": False, "line1": None, "line2": None}))
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("F: marker + script active:false returns []")
    else:
        fail(f"F: expected [], got {r!r}")


# G: marker present + script returns active:true but missing line1/line2 keys -> []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_mock_script(td, emit_json_script({"active": True}))
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("G: marker + script active:true but missing line1/line2 returns []")
    else:
        fail(f"G: expected [], got {r!r}")


# H: env var RABBIT_AUTO_EVOLVE_REPO_ROOT is set so banner-status.py inspects
#    the tempdir markers, not the test process CWD. Verify by writing a mock
#    script that echoes that env var into line1.text and asserting it equals td.
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_mock_script(td, (
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "root = os.environ.get('RABBIT_AUTO_EVOLVE_REPO_ROOT', '<unset>')\n"
        "sys.stdout.write(json.dumps({\n"
        "  'active': True,\n"
        "  'line1': {'text': root, 'icon': 'I', 'color': 'red'},\n"
        "  'line2': {'text': 'L2', 'icon': 'J', 'color': 'yellow'},\n"
        "}))\n"
        "sys.exit(0)\n"
    ))
    r = emit_auto_evolve_banner(repo_root=td)
    if len(r) == 2 and r[0].get("text") == td:
        ok("H: RABBIT_AUTO_EVOLVE_REPO_ROOT propagates repo_root into subprocess env")
    else:
        fail(f"H: expected line1.text == {td!r}, got {r!r}")


if FAIL:
    print("test-runtime-emit-auto-evolve-banner: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-auto-evolve-banner: all checks passed.")
