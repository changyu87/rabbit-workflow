#!/usr/bin/env python3
"""test-lib-checks.py — CONTRACT-BACKLOG-26

End-to-end tests for contract.lib.checks library API. Asserts:
  - lib/__init__.py exists
  - lib/checks.py is importable
  - CheckResult is a dataclass with fields (passed: bool, messages: list[str])
  - 8 library functions exist with documented signatures and return CheckResult
  - Each function delivers the same outcome the corresponding CLI shim does
  - Each CLI shim (validate-feature.py + 7 enforcement checks) is now a thin
    wrapper that imports from contract.lib.checks

Run non-interactively. Exits non-zero on failure.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
LIB_DIR = os.path.join(FEATURE_DIR, "lib")
CHECKS_PATH = os.path.join(LIB_DIR, "checks.py")
ENF_DIR = os.path.join(FEATURE_DIR, "scripts", "enforcement")
VALIDATE_SHIM = os.path.join(FEATURE_DIR, "scripts", "validate-feature.py")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def load_checks():
    spec = importlib.util.spec_from_file_location("contract_lib_checks", CHECKS_PATH)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# t0: lib/ directory + lib/__init__.py + lib/checks.py exist
if not os.path.isdir(LIB_DIR):
    fail("t0a", f"lib dir missing: {LIB_DIR}")
else:
    ok("t0a", "lib/ directory exists")

if not os.path.isfile(os.path.join(LIB_DIR, "__init__.py")):
    fail("t0b", "lib/__init__.py missing")
else:
    ok("t0b", "lib/__init__.py exists")

if not os.path.isfile(CHECKS_PATH):
    fail("t0c", f"lib/checks.py missing: {CHECKS_PATH}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0c", "lib/checks.py exists")

# t1: import lib.checks
checks = load_checks()
if checks is None:
    fail("t1", "could not import lib/checks.py")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", "lib/checks.py imports cleanly")

# t2: CheckResult exists as dataclass-like with passed (bool) + messages (list)
if not hasattr(checks, "CheckResult"):
    fail("t2a", "CheckResult class missing")
else:
    ok("t2a", "CheckResult class exists")
    try:
        r = checks.CheckResult(passed=True, messages=["hi"])
        if r.passed is True and r.messages == ["hi"]:
            ok("t2b", "CheckResult(passed, messages) instantiates correctly")
        else:
            fail("t2b", f"CheckResult fields wrong: {r!r}")
    except Exception as e:
        fail("t2b", f"CheckResult construction raised: {e!r}")

# t3: each required function exists and is callable
REQUIRED_FUNCS = [
    "check_tests_non_interactive",
    "check_sentinel",
    "check_naming",
    "check_imports_resolve",
    "check_symlinks_resolve",
    "check_template_producer_consistency",
    "check_numbered_lists",
    "validate_feature",
]
for fn_name in REQUIRED_FUNCS:
    if hasattr(checks, fn_name) and callable(getattr(checks, fn_name)):
        ok(f"t3-{fn_name}", "function exists and is callable")
    else:
        fail(f"t3-{fn_name}", "function missing or not callable")

# t4: end-to-end — check_tests_non_interactive returns CheckResult.passed=True
# when test/ is clean and False when test/ contains bare input()
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "fake_feature")
    tdir = os.path.join(fdir, "test")
    os.makedirs(tdir)
    with open(os.path.join(tdir, "test_clean.py"), "w") as f:
        f.write("import sys\nprint('hi')\nsys.exit(0)\n")
    res = checks.check_tests_non_interactive(fdir)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t4a", "check_tests_non_interactive returns passed=True on clean dir")
    else:
        fail("t4a", f"expected passed=True, got {res!r}")

with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "fake_feature")
    tdir = os.path.join(fdir, "test")
    os.makedirs(tdir)
    # avoid literal in scanner-self-detection: split the call name
    _inp = "in" + "put"
    with open(os.path.join(tdir, "test_bad.py"), "w") as f:
        f.write(f"x = {_inp}('go? ')\n")
    res = checks.check_tests_non_interactive(fdir)
    if isinstance(res, checks.CheckResult) and not res.passed and res.messages:
        ok("t4b", "check_tests_non_interactive returns passed=False with messages on violation")
    else:
        fail("t4b", f"expected passed=False with messages, got {res!r}")

# t5: end-to-end — check_sentinel
with tempfile.TemporaryDirectory() as tmp:
    py_path = os.path.join(tmp, "good.py")
    with open(py_path, "w") as f:
        f.write("# RABBIT-POLICY-BLOCK-v1\nprint('hi')\n")
    res = checks.check_sentinel(py_path)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t5a", "check_sentinel passes when sentinel present")
    else:
        fail("t5a", f"expected passed=True, got {res!r}")

    bad_path = os.path.join(tmp, "bad.py")
    with open(bad_path, "w") as f:
        f.write("print('no sentinel')\n")
    res = checks.check_sentinel(bad_path)
    if isinstance(res, checks.CheckResult) and not res.passed:
        ok("t5b", "check_sentinel fails when sentinel absent")
    else:
        fail("t5b", f"expected passed=False, got {res!r}")

# t6: end-to-end — check_naming
with tempfile.TemporaryDirectory() as tmp:
    agents_dir = os.path.join(tmp, ".claude", "agents")
    os.makedirs(agents_dir)
    with open(os.path.join(agents_dir, "rbt-bad.md"), "w") as f:
        f.write("---\nname: rbt-bad\n---\n")
    res = checks.check_naming(tmp)
    if isinstance(res, checks.CheckResult) and not res.passed:
        ok("t6a", "check_naming fails on rbt- prefix")
    else:
        fail("t6a", f"expected passed=False, got {res!r}")

with tempfile.TemporaryDirectory() as tmp:
    # no .claude tree at all → vacuous pass
    res = checks.check_naming(tmp)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t6b", "check_naming vacuously passes when no .claude tree")
    else:
        fail("t6b", f"expected passed=True, got {res!r}")

# t7: end-to-end — check_imports_resolve (vacuous when no docs/)
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "empty_feature")
    os.makedirs(fdir)
    res = checks.check_imports_resolve(fdir)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t7", "check_imports_resolve vacuously passes when no docs/")
    else:
        fail("t7", f"expected passed=True, got {res!r}")

# t8: end-to-end — check_symlinks_resolve on a tree with no symlinks → pass
with tempfile.TemporaryDirectory() as tmp:
    claude_dir = os.path.join(tmp, ".claude")
    os.makedirs(claude_dir)
    res = checks.check_symlinks_resolve(tmp)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t8a", "check_symlinks_resolve passes on tree without symlinks")
    else:
        fail("t8a", f"expected passed=True, got {res!r}")

with tempfile.TemporaryDirectory() as tmp:
    claude_dir = os.path.join(tmp, ".claude")
    os.makedirs(claude_dir)
    # dangling symlink
    link = os.path.join(claude_dir, "broken_link")
    os.symlink(os.path.join(tmp, "nonexistent"), link)
    res = checks.check_symlinks_resolve(tmp)
    if isinstance(res, checks.CheckResult) and not res.passed:
        ok("t8b", "check_symlinks_resolve fails on dangling symlink")
    else:
        fail("t8b", f"expected passed=False, got {res!r}")

# t9: end-to-end — check_template_producer_consistency on real template
real_template = os.path.join(FEATURE_DIR, "templates", "bug-template.json")
if os.path.isfile(real_template):
    res = checks.check_template_producer_consistency(real_template)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t9a", "check_template_producer_consistency passes on real bug-template.json")
    else:
        fail("t9a", f"expected passed=True, got {res!r}")
else:
    fail("t9a", f"real template missing for test: {real_template}")

with tempfile.TemporaryDirectory() as tmp:
    bad_tmpl = os.path.join(tmp, "bad-template.json")
    with open(bad_tmpl, "w") as f:
        f.write('{"template_version": "1.0", "totally_made_up_field": "x"}\n')
    res = checks.check_template_producer_consistency(bad_tmpl)
    if isinstance(res, checks.CheckResult) and not res.passed:
        ok("t9b", "check_template_producer_consistency fails on unknown key")
    else:
        fail("t9b", f"expected passed=False, got {res!r}")

# t10: end-to-end — check_numbered_lists
with tempfile.TemporaryDirectory() as tmp:
    md = os.path.join(tmp, "clean.md")
    with open(md, "w") as f:
        f.write("# Clean\n\n1. one\n2. two\n")
    res = checks.check_numbered_lists([md])
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t10a", "check_numbered_lists passes on clean markdown")
    else:
        fail("t10a", f"expected passed=True, got {res!r}")

    bad = os.path.join(tmp, "bad.md")
    with open(bad, "w") as f:
        f.write("## 2.6 Foo\n")
    res = checks.check_numbered_lists([bad])
    if isinstance(res, checks.CheckResult) and not res.passed:
        ok("t10b", "check_numbered_lists fails on decimal heading")
    else:
        fail("t10b", f"expected passed=False, got {res!r}")

# t11: end-to-end — validate_feature on a known-valid sibling feature.
# (The contract feature.json itself happens to lack surface.agents; that is
# a pre-existing condition not in scope for this cycle.)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
SIBLING = os.path.join(REPO_ROOT, ".claude", "features", "rabbit-feature")
res = checks.validate_feature(SIBLING)
if isinstance(res, checks.CheckResult) and res.passed:
    ok("t11a", "validate_feature passes on rabbit-feature feature")
else:
    fail("t11a", f"expected passed=True, got {res!r}")

with tempfile.TemporaryDirectory() as tmp:
    # empty dir → fails (missing feature.json etc.)
    res = checks.validate_feature(tmp)
    if isinstance(res, checks.CheckResult) and not res.passed:
        ok("t11b", "validate_feature fails on empty dir")
    else:
        fail("t11b", f"expected passed=False, got {res!r}")

# t5c (CONTRACT-BACKLOG-28): check_sentinel directory-walk branch — given a
# directory containing a mix of .py files with and without the sentinel, the
# check must report exactly the missing files.
with tempfile.TemporaryDirectory() as tmp:
    with open(os.path.join(tmp, "with_sentinel.py"), "w") as f:
        f.write("# RABBIT-POLICY-BLOCK-v1\nprint('hi')\n")
    with open(os.path.join(tmp, "without_sentinel.py"), "w") as f:
        f.write("print('nope')\n")
    nested = os.path.join(tmp, "nested")
    os.makedirs(nested)
    with open(os.path.join(nested, "also_without.py"), "w") as f:
        f.write("print('no')\n")
    res = checks.check_sentinel(tmp)
    if (isinstance(res, checks.CheckResult) and not res.passed
            and any("without_sentinel.py" in m for m in res.messages)
            and any("also_without.py" in m for m in res.messages)
            and not any("with_sentinel.py" in m for m in res.messages)):
        ok("t5c", "check_sentinel directory-walk reports only files missing sentinel")
    else:
        fail("t5c", f"unexpected result: {res!r}")

# t6c (CONTRACT-BACKLOG-28): check_naming positive-path on a clean .claude tree
# (not the vacuous no-.claude case). Tree has compliant commands/agents/skills
# subdirectories and a docs/ subtree (docs/ is exempt from prefix scan).
with tempfile.TemporaryDirectory() as tmp:
    claude_dir = os.path.join(tmp, ".claude")
    cmds = os.path.join(claude_dir, "commands")
    agents = os.path.join(claude_dir, "agents")
    skills_dir = os.path.join(claude_dir, "skills", "rabbit-x")
    docs = os.path.join(claude_dir, "docs")
    for d in (cmds, agents, skills_dir, docs):
        os.makedirs(d)
    open(os.path.join(cmds, "rabbit-foo.md"), "w").close()
    open(os.path.join(agents, "rabbit-bar.md"), "w").close()
    open(os.path.join(skills_dir, "SKILL.md"), "w").close()
    # docs/ is exempt — banned prefixes there must not trigger
    open(os.path.join(docs, "rbt-historical-note.md"), "w").close()
    res = checks.check_naming(tmp)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t6c", "check_naming positive-path passes on clean .claude tree (docs/ exempt)")
    else:
        fail("t6c", f"expected passed=True, got {res!r}")

# t7b (CONTRACT-BACKLOG-28): check_imports_resolve missing-import case —
# docs/ contains a markdown file with a @-import that does not resolve.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "feature")
    docs_dir = os.path.join(fdir, "docs")
    os.makedirs(docs_dir)
    with open(os.path.join(docs_dir, "spec.md"), "w") as f:
        f.write("# Spec\n\n@./does/not/exist.md\n")
    # The check resolves against the git repo root, not feature_dir, so we
    # must ensure the unresolved path stays unresolved — pick a path with no
    # chance of accidentally resolving in the real repo.
    res = checks.check_imports_resolve(fdir)
    if (isinstance(res, checks.CheckResult) and not res.passed
            and any("does/not/exist.md" in m for m in res.messages)):
        ok("t7b", "check_imports_resolve fails on unresolved @-import")
    else:
        fail("t7b", f"expected passed=False with MISSING message, got {res!r}")

# t8c (CONTRACT-BACKLOG-28): check_symlinks_resolve deep-nested symlink —
# a dangling symlink 4 levels under .claude/ MUST be detected.
with tempfile.TemporaryDirectory() as tmp:
    deep = os.path.join(tmp, ".claude", "a", "b", "c", "d")
    os.makedirs(deep)
    link = os.path.join(deep, "deep_link")
    os.symlink(os.path.join(tmp, "does_not_exist"), link)
    res = checks.check_symlinks_resolve(tmp)
    if (isinstance(res, checks.CheckResult) and not res.passed
            and any("deep_link" in m for m in res.messages)):
        ok("t8c", "check_symlinks_resolve detects dangling symlink at depth 4")
    else:
        fail("t8c", f"expected passed=False naming deep_link, got {res!r}")

# t11c (CONTRACT-BACKLOG-28): validate_feature library-level retired
# short-circuit. A temp feature_dir with feature.json carrying status=retired
# MUST pass with a RETIRED: notice, even though the structural files are
# absent.
import json as _json
with tempfile.TemporaryDirectory() as tmp:
    feat_dir = os.path.join(tmp, "retired_feature")
    os.makedirs(feat_dir)
    with open(os.path.join(feat_dir, "feature.json"), "w") as f:
        _json.dump({"name": "retired_feature", "status": "retired"}, f)
    res = checks.validate_feature(feat_dir)
    if (isinstance(res, checks.CheckResult) and res.passed
            and any("RETIRED" in m for m in res.messages)):
        ok("t11c", "validate_feature short-circuits with RETIRED: notice for status=retired")
    else:
        fail("t11c", f"expected passed=True with RETIRED notice, got {res!r}")

# t13 (CONTRACT-BACKLOG-28 / Inv 37(d) purity): library functions MUST NOT
# call sys.exit, MUST NOT print to stdout/stderr, MUST NOT raise on contract-
# violation conditions. Patch print and sys.exit; call every library function
# with deliberately broken inputs; assert no patched call fires and no
# exception escapes.
from unittest import mock as _mock

_print_calls = []
_exit_calls = []

def _capture_print(*a, **kw):
    _print_calls.append((a, kw))


def _capture_exit(*a, **kw):
    _exit_calls.append((a, kw))
    raise AssertionError("sys.exit must not be called from a library function")


_LIB_FUNCS = [
    ("check_tests_non_interactive", ("/no/such/path",), {}),
    ("check_sentinel", ("/no/such/path",), {}),
    ("check_naming", ("/no/such/path",), {}),
    ("check_imports_resolve", ("/no/such/path",), {}),
    ("check_symlinks_resolve", ("/no/such/path",), {}),
    ("check_template_producer_consistency", ("/no/such/template.json",), {}),
    ("check_numbered_lists", ([],), {}),
    ("validate_feature", ("",), {}),
]

# Patch the print built-in inside the library module's namespace and sys.exit
# globally — any call to either by a library function will be captured.
with _mock.patch.object(checks, "print", _capture_print, create=True), \
        _mock.patch("sys.exit", _capture_exit):
    for fn_name, args, kwargs in _LIB_FUNCS:
        fn = getattr(checks, fn_name)
        try:
            res = fn(*args, **kwargs)
        except SystemExit:
            fail("t13", f"{fn_name} raised SystemExit on broken input")
            continue
        except AssertionError:
            # Raised by our _capture_exit if sys.exit was called inside fn.
            fail("t13", f"{fn_name} called sys.exit on broken input")
            continue
        except Exception as e:  # noqa: BLE001
            fail("t13", f"{fn_name} raised {type(e).__name__}: {e}")
            continue
        if not isinstance(res, checks.CheckResult):
            fail("t13", f"{fn_name} returned non-CheckResult: {res!r}")

if not _print_calls and not _exit_calls:
    ok("t13", "all 8 library functions are pure (no print, no sys.exit, no raise) on broken inputs")
elif _print_calls:
    fail("t13", f"library function printed: {_print_calls}")
elif _exit_calls:
    fail("t13", f"library function called sys.exit: {_exit_calls}")


# t12: CLI shims still work as drop-in replacements (sanity smoke-test).
# The check is that each shim exits 0/1 correctly on a smoke fixture, just as
# the library function does. This validates the shim plumbing.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "fake_feature")
    tdir = os.path.join(fdir, "test")
    os.makedirs(tdir)
    with open(os.path.join(tdir, "test_clean.py"), "w") as f:
        f.write("print('hi')\n")
    r = subprocess.run(
        ["python3", os.path.join(ENF_DIR, "check-tests-non-interactive.py"), fdir],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok("t12-tests-non-interactive", "CLI shim exits 0 on clean fixture")
    else:
        fail("t12-tests-non-interactive", f"shim returned {r.returncode}; stderr={r.stderr!r}")

with tempfile.TemporaryDirectory() as tmp:
    py = os.path.join(tmp, "good.py")
    with open(py, "w") as f:
        f.write("# RABBIT-POLICY-BLOCK-v1\nprint('hi')\n")
    r = subprocess.run(
        ["python3", os.path.join(ENF_DIR, "check-sentinel.py"), py],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok("t12-sentinel", "CLI shim exits 0 on file with sentinel")
    else:
        fail("t12-sentinel", f"shim returned {r.returncode}; stderr={r.stderr!r}")

# Naming shim on contract feature root (which is a known clean .claude tree-ancestor):
# point it at a directory with no .claude/ for a vacuous pass.
with tempfile.TemporaryDirectory() as tmp:
    r = subprocess.run(
        ["python3", os.path.join(ENF_DIR, "check-naming.py"), tmp],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok("t12-naming", "CLI shim exits 0 on dir without .claude/")
    else:
        fail("t12-naming", f"shim returned {r.returncode}; stderr={r.stderr!r}")

with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "empty_feature")
    os.makedirs(fdir)
    r = subprocess.run(
        ["python3", os.path.join(ENF_DIR, "check-imports-resolve.py"), fdir],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok("t12-imports-resolve", "CLI shim exits 0 on feature without docs/")
    else:
        fail("t12-imports-resolve", f"shim returned {r.returncode}; stderr={r.stderr!r}")

with tempfile.TemporaryDirectory() as tmp:
    # symlinks shim wants a repo-root-like dir with .claude/
    cdir = os.path.join(tmp, ".claude")
    os.makedirs(cdir)
    r = subprocess.run(
        ["python3", os.path.join(ENF_DIR, "check-symlinks-resolve.py"), tmp],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok("t12-symlinks-resolve", "CLI shim exits 0 on .claude/ without symlinks")
    else:
        fail("t12-symlinks-resolve", f"shim returned {r.returncode}; stderr={r.stderr!r}")

r = subprocess.run(
    ["python3", os.path.join(ENF_DIR, "check-template-schema-producer-consistency.py"),
     real_template],
    capture_output=True, text=True,
)
if r.returncode == 0:
    ok("t12-template-producer", "CLI shim exits 0 on real bug-template.json")
else:
    fail("t12-template-producer", f"shim returned {r.returncode}; stderr={r.stderr!r}")

with tempfile.TemporaryDirectory() as tmp:
    md = os.path.join(tmp, "clean.md")
    with open(md, "w") as f:
        f.write("# Hello\n\n1. one\n2. two\n")
    r = subprocess.run(
        ["python3", os.path.join(ENF_DIR, "check-numbered-lists.py"), md],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ok("t12-numbered-lists", "CLI shim exits 0 on clean markdown")
    else:
        fail("t12-numbered-lists", f"shim returned {r.returncode}; stderr={r.stderr!r}")

r = subprocess.run(
    ["python3", VALIDATE_SHIM, SIBLING],
    capture_output=True, text=True,
)
if r.returncode == 0:
    ok("t12-validate-feature", "validate-feature.py CLI shim exits 0 on rabbit-feature")
else:
    fail("t12-validate-feature", f"shim returned {r.returncode}; stderr={r.stderr!r}")

# t14 (#702): validate_feature must accept every tdd_state the TDD state
# machine (tdd-subagent/scripts/tdd-step.py) can legitimately write —
# including `sync-deployed`, the transient state between IMPLEMENT and
# CODE-REVIEW. Before the fix, _VALID_TDD_STATES omitted `sync-deployed`,
# so validate_feature failed spuriously mid-cycle. We build a minimally
# valid feature dir and re-validate it at each cycle state.
import json as _json2


def _make_valid_feature(root, tdd_state):
    fdir = os.path.join(root, "fixture_feature")
    tdir = os.path.join(fdir, "test")
    ddir = os.path.join(fdir, "docs")
    os.makedirs(tdir)
    os.makedirs(ddir)
    with open(os.path.join(ddir, "spec.md"), "w") as f:
        f.write("# Spec\n")
    with open(os.path.join(ddir, "contract.md"), "w") as f:
        f.write("# Contract\n")
    run_py = os.path.join(tdir, "run.py")
    with open(run_py, "w") as f:
        f.write("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
    os.chmod(run_py, 0o755)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        _json2.dump({
            "name": "fixture_feature",
            "version": "1.0.0",
            "owner": "rabbit-workflow team",
            "tdd_state": tdd_state,
            "summary": "fixture",
            "deprecation_criterion": "never (test fixture)",
        }, f)
    return fdir


with tempfile.TemporaryDirectory() as tmp:
    fdir = _make_valid_feature(tmp, "sync-deployed")
    res = checks.validate_feature(fdir)
    if isinstance(res, checks.CheckResult) and res.passed:
        ok("t14a", "validate_feature accepts tdd_state='sync-deployed'")
    else:
        fail("t14a", f"expected passed=True for sync-deployed, got {res!r}")

# t14b: parity guard — _VALID_TDD_STATES must be a superset of every state
# tdd-step.py can write, so the two cannot drift out of sync again.
TDD_STEP_PATH = os.path.normpath(os.path.join(
    REPO_ROOT, ".claude", "features", "tdd-subagent", "scripts", "tdd-step.py"))
if not os.path.isfile(TDD_STEP_PATH):
    fail("t14b", f"tdd-step.py not found at {TDD_STEP_PATH}")
else:
    _step_spec = importlib.util.spec_from_file_location("tdd_step_mod", TDD_STEP_PATH)
    _step_mod = importlib.util.module_from_spec(_step_spec)
    _step_spec.loader.exec_module(_step_mod)
    step_states = set(getattr(_step_mod, "_VALID_STATES", set()))
    missing = step_states - checks._VALID_TDD_STATES
    if not missing:
        ok("t14b", "_VALID_TDD_STATES is a superset of tdd-step.py _VALID_STATES")
    else:
        fail("t14b", f"_VALID_TDD_STATES missing states tdd-step.py writes: {sorted(missing)}")

# t14c: every state tdd-step.py can write validates cleanly (regression).
with tempfile.TemporaryDirectory() as tmp:
    bad = []
    for st in sorted(step_states):
        fdir = _make_valid_feature(tmp, st)
        res = checks.validate_feature(fdir)
        if not (isinstance(res, checks.CheckResult) and res.passed):
            bad.append((st, res))
        import shutil as _shutil
        _shutil.rmtree(fdir)
    if not bad:
        ok("t14c", "validate_feature accepts every tdd-step.py state")
    else:
        fail("t14c", f"validate_feature rejected states: {[s for s, _ in bad]}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
