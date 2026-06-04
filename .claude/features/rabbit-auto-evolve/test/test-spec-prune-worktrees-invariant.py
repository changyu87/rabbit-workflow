#!/usr/bin/env python3
"""test-spec-prune-worktrees-invariant.py — rabbit-auto-evolve Inv 53 (#628).

Asserts that docs/spec.md, docs/contract.md, and run-tick-phases.py document
and wire the tick-start orphan sweep introduced for issue #628:

  1. spec.md carries Inv 53 with the sweep script name, the `agent-*` scope,
     the under-`.claude/worktrees/`-only / never-touch-the-main-checkout
     safety constraint, the tick-start pre-dispatch sequencing, and the
     prompt-dir bounding via the contract cleanup invoke.
  2. contract.md `invokes.modules` declares the cross-scope
     contract.lib.runtime.cleanup_old_prompts call (rabbit-auto-evolve does
     not edit the contract feature).
  3. run-tick-phases.py's pre-dispatch segment actually invokes
     prune-worktrees.py (the sweep is wired in, not just documented).

This is the spec-level regression guarding the sweep contract; the behavioral
e2e lives in test-prune-worktrees.py.
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "contract.md"
RUN_TICK = FEATURE_DIR / "scripts" / "run-tick-phases.py"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) spec.md carries Inv 53 -----------------------------------------
spec_low = norm(SPEC_MD.read_text()).lower()

SPEC_REQUIRED = [
    "inv 53",
    "prune-worktrees.py",
    "agent-*",
    ".claude/worktrees/",
    "tick start",
    "pre-dispatch",
    "cleanup_old_prompts",
    "git worktree remove",
]
missing = [s for s in SPEC_REQUIRED if s not in spec_low]
if missing:
    fail(f"spec.md missing Inv 53 phrase(s): {missing!r}")
else:
    ok("spec.md carries Inv 53 with sweep script, agent-* scope, "
       "tick-start sequencing, and prompt-bounding invoke")

# The sweep must be documented as NEVER removing the main checkout.
if "main checkout" in spec_low and "never" in spec_low:
    ok("spec.md documents the sweep never removes the main checkout")
else:
    fail("spec.md does not state the sweep never removes the main checkout")

# The sweep must be documented as never failing the tick on a sweep error.
if "never" in spec_low and ("block" in spec_low or "fail the tick" in spec_low):
    ok("spec.md documents disk hygiene must never block the tick")
else:
    fail("spec.md does not state the sweep never blocks/fails the tick")

# --- (2) contract.md invokes.modules declares the cleanup call ----------
contract_text = CONTRACT_MD.read_text()
m = re.search(r"```json\s*(\{.*?\})\s*```", contract_text, re.DOTALL)
if not m:
    fail("contract.md has no parseable JSON block")
else:
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        obj = None
        fail(f"contract.md JSON block does not parse: {e}")
    if obj is not None:
        modules = obj.get("invokes", {}).get("modules", [])
        runtime = [d for d in modules if isinstance(d, dict)
                   and "contract/lib/runtime.py" in d.get("path", "")
                   and d.get("function") == "cleanup_old_prompts"]
        if runtime:
            ok("contract.md invokes.modules declares "
               "contract.lib.runtime.cleanup_old_prompts")
        else:
            fail("contract.md invokes.modules missing the "
                 f"cleanup_old_prompts cross-scope invoke: {modules!r}")

# --- (3) run-tick-phases.py wires the sweep into pre-dispatch -----------
run_tick = RUN_TICK.read_text()
if "prune-worktrees.py" not in run_tick:
    fail("run-tick-phases.py does not invoke prune-worktrees.py")
else:
    # The invocation must appear inside run_pre_dispatch (tick start), not
    # post-dispatch. Slice the pre-dispatch function body and check there.
    pre_start = run_tick.find("def run_pre_dispatch")
    post_start = run_tick.find("def run_post_dispatch")
    pre_body = run_tick[pre_start:post_start] if pre_start != -1 else ""
    # The sweep is invoked via the _run_prune_worktrees helper from within the
    # pre-dispatch body; the helper itself resolves prune-worktrees.py.
    if pre_start == -1 or post_start == -1:
        fail("run-tick-phases.py missing run_pre_dispatch/run_post_dispatch")
    elif "_run_prune_worktrees(" in pre_body:
        ok("run-tick-phases.py invokes the prune-worktrees sweep in the "
           "pre-dispatch (tick-start) segment")
    else:
        fail("prune-worktrees sweep is wired but NOT in the pre-dispatch "
             "segment")

print()
sys.exit(FAIL)
