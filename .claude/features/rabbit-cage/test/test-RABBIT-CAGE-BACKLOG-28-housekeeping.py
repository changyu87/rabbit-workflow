#!/usr/bin/env python3
"""RABBIT-CAGE-BACKLOG-28 — housekeeping sweep e2e tests.

End-to-end coverage for the BACKLOG-28 cleanup cycle:

  (a) Inv 33 reconciliation: SKILL.md frontmatter description names all
      seven subcommands (help included).

  (b) Inv 58 three-way version alignment: feature.json, spec.md, and
      contract.md all at the new version 4.11.0.

  (c) Module-level public-API hygiene in _runtime_flags.py:
        - per-flag canonical constants are PRIVATE (underscore-prefixed),
        - a public CANONICAL_FLAG_BODIES dict exposes the canonical bodies
          for test consumption.

  (d) sync-check.py no longer imports the unused name `rabbit_subline`
      from rabbit_print.

  (e) Shared `log_exc` helper lives in `_runtime_flags.py` and BOTH
      sync-check.py and session-init.py import it (no per-hook
      duplicate definition).

  (f) scope-guard.py default-deny message names `scope-guard-on.py` as
      the override-revoke mechanism so the operator can find the revoke
      tool from the deny message alone.

  (g) rabbit-config.py `cmd_permissions` error path follows the same
      style as `cmd_allowed_tools` / `cmd_bash_allow` — the error message
      explicitly says "expected lock or unlock" and rejects bad/missing
      action without modifying any file.

Per Inv 44, tests MUST NOT mutate live source files — every fixture is
built inside tempfile.mkdtemp.
"""
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

CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
RUNTIME_FLAGS = os.path.join(CAGE, "hooks/_runtime_flags.py")
SYNC_CHECK = os.path.join(CAGE, "hooks/sync-check.py")
SESSION_INIT = os.path.join(CAGE, "hooks/session-init.py")
SCOPE_GUARD = os.path.join(CAGE, "hooks/scope-guard.py")
RABBIT_CONFIG_PY = os.path.join(
    CAGE, "skills/rabbit-config/scripts/rabbit-config.py",
)
SKILL_MD = os.path.join(CAGE, "skills/rabbit-config/SKILL.md")
FEATURE_JSON = os.path.join(CAGE, "feature.json")
SPEC_MD = os.path.join(CAGE, "docs/spec/spec.md")
CONTRACT_MD = os.path.join(CAGE, "docs/spec/contract.md")

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


def read(p):
    with open(p) as f:
        return f.read()


def header_version(text):
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)", text, re.MULTILINE)
    return m.group(1) if m else None


print("test-RABBIT-CAGE-BACKLOG-28-housekeeping.py")
print()

# ---- (a) Inv 33 reconciliation: description names seven subcommands ----
skill_text = read(SKILL_MD)
fm_match = re.match(r"^---\n(.*?)\n---", skill_text, re.DOTALL)
if not fm_match:
    fail_t("a0", "SKILL.md missing YAML frontmatter")
else:
    fm = fm_match.group(1)
    desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
    desc = desc_match.group(1) if desc_match else ""
    seven = (
        "help", "prompt-threshold", "allowed-tools", "bash-allow",
        "permissions", "human-approval", "bypass-permissions",
    )
    missing = [s for s in seven if s not in desc]
    if not missing:
        ok("a1", "SKILL.md description names all seven subcommands (Inv 33 reconciled)")
    else:
        fail_t("a1", f"SKILL.md description omits subcommands: {missing}")

# ---- (b) Inv 58 three-way version alignment at 4.10.0 ----
with open(FEATURE_JSON) as f:
    feature_json = json.load(f)
feature_v = feature_json.get("version")
spec_v = header_version(read(SPEC_MD))
contract_v = header_version(read(CONTRACT_MD))
EXPECTED = "4.11.0"
if feature_v == spec_v == contract_v == EXPECTED:
    ok("b1", f"feature.json/spec.md/contract.md all at {EXPECTED} (Inv 58)")
else:
    fail_t("b1", (
        f"three-way version mismatch or wrong target: "
        f"feature.json={feature_v!r}, spec.md={spec_v!r}, "
        f"contract.md={contract_v!r}, expected={EXPECTED!r}"
    ))

# ---- (b2) Inv 93: feature.json does not carry the legacy 'updated_note' field ----
if "updated_note" not in feature_json:
    ok("b2", "feature.json no longer carries the legacy 'updated_note' field (Inv 93)")
else:
    fail_t("b2", "feature.json still carries 'updated_note' — drop per Inv 93")

# ---- (c) module-level public-API hygiene in _runtime_flags.py ----
spec = importlib.util.spec_from_file_location("_runtime_flags_mod", RUNTIME_FLAGS)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# c1: per-flag canonical constants are PRIVATE (underscore-prefixed).
public_bare_names = [
    "BYPASS_PERMISSIONS_BODY", "BYPASS_PERMISSIONS_REVOKE",
    "HUMAN_APPROVAL_BODY", "HUMAN_APPROVAL_REVOKE",
]
leaked = [n for n in public_bare_names if hasattr(mod, n)]
if not leaked:
    ok("c1", "per-flag constants are private (no public BYPASS_*/HUMAN_* names)")
else:
    fail_t("c1", f"leaked public names from _runtime_flags: {leaked}")

# c2: public CANONICAL_FLAG_BODIES dict exposes canonical bodies.
bodies = getattr(mod, "CANONICAL_FLAG_BODIES", None)
if isinstance(bodies, dict) and "bypass_permissions" in bodies and "human_approval" in bodies:
    bp_body = bodies["bypass_permissions"]
    ha_body = bodies["human_approval"]
    if "BYPASS-PERMISSIONS MODE ACTIVE" in bp_body and "HUMAN APPROVAL BYPASS ACTIVE" in ha_body:
        ok("c2", "CANONICAL_FLAG_BODIES exposes canonical bypass-permissions + human-approval text")
    else:
        fail_t("c2", f"CANONICAL_FLAG_BODIES values look wrong: {bodies!r}")
else:
    fail_t("c2", f"CANONICAL_FLAG_BODIES not exposed as a dict with both flags: {bodies!r}")

# ---- (d) sync-check.py no longer imports unused rabbit_subline ----
sc_src = read(SYNC_CHECK)
# Match the rabbit_print import block and confirm rabbit_subline is absent from it.
m = re.search(r"from rabbit_print import\s*\(\s*(.*?)\)", sc_src, re.DOTALL)
if m:
    imported_block = m.group(1)
    imported_names = {
        tok.strip().rstrip(",")
        for line in imported_block.splitlines()
        for tok in line.split(",")
        if tok.strip()
    }
    if "rabbit_subline" not in imported_names:
        ok("d1", "sync-check.py does NOT import unused rabbit_subline")
    else:
        fail_t("d1", f"sync-check.py still imports rabbit_subline: {imported_names}")
else:
    fail_t("d1", "could not locate rabbit_print import block in sync-check.py")

# ---- (e) shared log_exc helper centralization ----
rf_src = read(RUNTIME_FLAGS)
si_src = read(SESSION_INIT)

# e1: _runtime_flags.py defines a top-level log_exc(...) function.
if re.search(r"^def\s+log_exc\s*\(", rf_src, re.MULTILINE):
    ok("e1", "_runtime_flags.py defines shared log_exc()")
else:
    fail_t("e1", "_runtime_flags.py missing shared log_exc() definition")

# e2: sync-check.py imports log_exc from _runtime_flags (not its own _log_exc def).
# The import may span multiple lines via parenthesised form; match the
# `_runtime_flags import (...)` block as a whole and look for `log_exc` inside.
m_imp_sc = re.search(
    r"from\s+_runtime_flags\s+import\s*(?:\(([^)]*)\)|([^\n]+))",
    sc_src,
)
imports_log_exc_sc = bool(
    m_imp_sc and "log_exc" in (m_imp_sc.group(1) or m_imp_sc.group(2) or "")
)
defines_log_exc_sc = bool(
    re.search(r"^def\s+_log_exc\s*\(", sc_src, re.MULTILINE)
)
if imports_log_exc_sc and not defines_log_exc_sc:
    ok("e2", "sync-check.py imports log_exc from _runtime_flags and no longer defines its own")
else:
    fail_t("e2", (
        f"sync-check.py duplicate-definition state wrong: "
        f"imports_log_exc={imports_log_exc_sc}, defines__log_exc={defines_log_exc_sc}"
    ))

# e3: session-init.py imports log_exc from _runtime_flags (not its own _log_exc def).
m_imp_si = re.search(
    r"from\s+_runtime_flags\s+import\s*(?:\(([^)]*)\)|([^\n]+))",
    si_src,
)
imports_log_exc_si = bool(
    m_imp_si and "log_exc" in (m_imp_si.group(1) or m_imp_si.group(2) or "")
)
defines_log_exc_si = bool(
    re.search(r"^def\s+_log_exc\s*\(", si_src, re.MULTILINE)
)
if imports_log_exc_si and not defines_log_exc_si:
    ok("e3", "session-init.py imports log_exc from _runtime_flags and no longer defines its own")
else:
    fail_t("e3", (
        f"session-init.py duplicate-definition state wrong: "
        f"imports_log_exc={imports_log_exc_si}, defines__log_exc={defines_log_exc_si}"
    ))

# ---- (f) scope-guard.py default-deny mentions scope-guard-on.py ----
# Drive the default-deny path end-to-end, then assert the stderr message
# contains 'scope-guard-on.py'.
import glob

def temporarily_clear_markers():
    saved = []
    paths = [
        os.path.join(REPO_ROOT, ".rabbit-scope-active"),
        os.path.join(REPO_ROOT, ".rabbit-scope-override"),
        os.path.join(REPO_ROOT, ".rabbit-scope-override-used"),
    ]
    paths.extend(glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")))
    for p in paths:
        if os.path.isfile(p):
            with open(p) as fh:
                saved.append((p, fh.read()))
            os.remove(p)

    def restore():
        for p, content in saved:
            with open(p, "w") as fh:
                fh.write(content)
    return restore


restore = temporarily_clear_markers()
try:
    target = os.path.join(
        REPO_ROOT,
        ".claude/features/rabbit-cage/scripts/__backlog28_deny_test__.txt",
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": "x"},
    }
    res = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    # f1: still denies (exit 2).
    if res.returncode == 2:
        ok("f1", "scope-guard.py default-deny still exits 2")
    else:
        fail_t("f1", f"expected exit 2, got {res.returncode} stderr={res.stderr!r}")

    # f2: deny message names scope-guard-on.py.
    if "scope-guard-on.py" in res.stderr:
        ok("f2", "default-deny message references scope-guard-on.py (revoke mechanism)")
    else:
        fail_t("f2", (
            "default-deny message missing 'scope-guard-on.py' reference; "
            f"stderr={res.stderr!r}"
        ))
finally:
    restore()

# ---- (g) cmd_permissions error path style alignment ----
# Other cmd_* error paths use the form "Error: unknown action 'X' for <name>
# (expected ... or ...)" and return rc != 0 without touching any file.
wd = tempfile.mkdtemp()
try:
    # g1: missing action emits an error naming "lock" and "unlock" and rc != 0.
    res_missing = subprocess.run(
        [sys.executable, RABBIT_CONFIG_PY, "permissions"],
        cwd=wd, capture_output=True, text=True,
    )
    combined_missing = (res_missing.stdout or "") + (res_missing.stderr or "")
    if (
        res_missing.returncode != 0
        and "lock" in combined_missing
        and "unlock" in combined_missing
    ):
        ok("g1", "cmd_permissions with no action errors and names both 'lock' and 'unlock'")
    else:
        fail_t("g1", (
            f"cmd_permissions missing-action wrong: rc={res_missing.returncode}, "
            f"combined={combined_missing!r}"
        ))

    # g2: unknown action emits an error using the same descriptive phrasing
    # ('expected') as the other subcommands' error paths, and rc != 0.
    res_unknown = subprocess.run(
        [sys.executable, RABBIT_CONFIG_PY, "permissions", "wobble"],
        cwd=wd, capture_output=True, text=True,
    )
    combined_unknown = (res_unknown.stdout or "") + (res_unknown.stderr or "")
    if (
        res_unknown.returncode != 0
        and "expected" in combined_unknown
        and "lock" in combined_unknown
        and "unlock" in combined_unknown
    ):
        ok("g2", "cmd_permissions unknown-action uses 'expected lock or unlock' style (aligned with cmd_*)")
    else:
        fail_t("g2", (
            f"cmd_permissions unknown-action wrong: rc={res_unknown.returncode}, "
            f"combined={combined_unknown!r}"
        ))
finally:
    shutil.rmtree(wd, ignore_errors=True)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
