#!/usr/bin/env python3
"""test-policy-block-lib.py — Inv 46

E2E test that contract.lib.policy_block.render_policy_block emits the
canonical framing (sentinel, header banner, per-file section separators,
footer banner) and embeds each named file's basename and content in order.

t1: render_policy_block returns a string containing the sentinel,
    MANDATORY POLICY header, each file's basename header line, each
    file's content, and the END POLICY footer in that order.
t2: render_policy_block on a missing path raises FileNotFoundError.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when policy assembly is native to Claude Code.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..")))

from lib.policy_block import render_policy_block  # noqa: E402

FAIL = 0


def ok(msg):
    print(f"PASS: {msg}")


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


# ---------- t1: framing + content order ----------
with tempfile.TemporaryDirectory() as td:
    a_path = os.path.join(td, "a.md")
    b_path = os.path.join(td, "b.md")
    a_body = "ALPHA-CONTENT-MARKER"
    b_body = "BETA-CONTENT-MARKER"
    with open(a_path, "w") as f:
        f.write(a_body)
    with open(b_path, "w") as f:
        f.write(b_body)

    output = render_policy_block([a_path, b_path])

    if not isinstance(output, str):
        fail(f"t1: render_policy_block must return str, got {type(output).__name__}")
    else:
        # framing tokens
        for token in (
            "RABBIT-POLICY-BLOCK-v1",
            "MANDATORY POLICY",
            "END POLICY",
            "a.md",
            "b.md",
            a_body,
            b_body,
        ):
            if token not in output:
                fail(f"t1: output missing required token: {token!r}")

        # ordering check: sentinel before header before a.md before alpha
        # before b.md before beta before footer
        order_tokens = [
            "RABBIT-POLICY-BLOCK-v1",
            "MANDATORY POLICY",
            "a.md",
            a_body,
            "b.md",
            b_body,
            "END POLICY",
        ]
        positions = [output.find(t) for t in order_tokens]
        if any(p < 0 for p in positions):
            fail(f"t1: one or more order tokens missing; positions={positions}")
        elif positions != sorted(positions):
            fail(f"t1: tokens out of order; positions={positions}")
        else:
            ok("t1: framing tokens and per-file content appear in order")

# ---------- t2: FileNotFoundError on missing path ----------
with tempfile.TemporaryDirectory() as td:
    missing = os.path.join(td, "does-not-exist.md")
    try:
        render_policy_block([missing])
        fail("t2: render_policy_block must raise FileNotFoundError on missing path")
    except FileNotFoundError:
        ok("t2: missing path raises FileNotFoundError")
    except Exception as e:
        fail(f"t2: expected FileNotFoundError, got {type(e).__name__}: {e}")

if FAIL:
    print("test-policy-block-lib: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-policy-block-lib: all checks passed.")
