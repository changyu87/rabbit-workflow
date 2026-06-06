#!/usr/bin/env python3
"""test-close-decomposed-parents.py — e2e tests for
scripts/close-decomposed-parents.py (Inv 53).

close-decomposed-parents.py reads, for every parent tracked in the state's
`decomposition_parents` map, the AUTHORITATIVE close-source: the GitHub-native
sub-issue rollup on the parent (`gh api repos/{slug}/issues/<parent>` ->
`sub_issues_summary{total, completed}`). When the parent has sub-issues and ALL
are complete (`total > 0 and completed == total`) it closes the parent
(`gh issue close <parent> --reason completed`) and drops the parent key. A
parent whose rollup is incomplete is left untouched.

COEXISTENCE (deprecating `decomposition_parents` mirror): a parent that carries
a `decomposition_parents` entry but has NO GitHub-native sub-issues yet
(`total == 0`) falls back to the legacy hand-rolled check — its recorded
children are queried individually via `gh issue view <child> --json state` and
the parent is closed only when EVERY recorded child is CLOSED.

Covered surface:

  - --help smoke
  - native rollup completed==total>0 -> parent CLOSED (gh issue close invoked
    with --reason completed) AND the parent key removed from
    decomposition_parents
  - native rollup completed<total -> parent NOT closed AND key RETAINED
  - mixed map (one complete rollup, one incomplete) -> only the complete
    parent is closed/removed
  - legacy coexistence: parent with a decomposition_parents entry but no native
    sub-issues (total==0) -> falls back to per-child gh issue view; all-closed
    children -> parent CLOSED + key dropped; one open child -> parent untouched
  - empty / absent decomposition_parents -> clean no-op (no gh issue close,
    exit 0)

Fixtures: a PATH-resident `gh` shim that (a) answers
`gh api repos/<slug>/issues/<n>` from a per-parent sub_issues_summary table
baked into the shim, (b) answers `gh issue view <n> --json state` from a
per-child state table, and (c) logs every `gh issue close ...` invocation to a
call log. State_dir is supplied via RABBIT_AUTO_EVOLVE_STATE_DIR.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "close-decomposed-parents.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _seed_state(state_dir, decomposition_parents):
    state = {
        "schema_version": "1.4.0",
        "updated_at": "2026-06-04T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
        "decomposition_parents": decomposition_parents,
    }
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f)


def _read_state(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        return json.load(f)


def _write_gh_shim(bin_dir, summaries, child_states, close_log):
    """Write a `gh` shim that:
      - answers `gh api repos/<slug>/issues/<n>` from `summaries`
        (parent-number string -> {"total": int, "completed": int}); a parent
        absent from `summaries` returns total=0 (no native sub-issues yet);
      - answers `gh issue view <n> --json state` from `child_states`
        (number -> "OPEN"/"CLOSED");
      - logs `gh issue close <n> ...` invocations (one argv line each) to
        close_log."""
    shim = os.path.join(bin_dir, "gh")
    py = [
        "#!/usr/bin/env python3",
        "import json, re, sys",
        f"SUMMARIES = {json.dumps({str(k): v for k, v in summaries.items()})}",
        f"STATES = {json.dumps({str(k): v for k, v in child_states.items()})}",
        f"CLOSE_LOG = {close_log!r}",
        "a = sys.argv[1:]",
        "if len(a) >= 2 and a[0] == 'api':",
        "    m = re.match(r'repos/[^/]+/[^/]+/issues/(\\d+)$', a[1])",
        "    if not m:",
        "        sys.stderr.write('unexpected api path: ' + a[1] + '\\n')",
        "        sys.exit(3)",
        "    num = m.group(1)",
        "    summ = SUMMARIES.get(num, {'total': 0, 'completed': 0})",
        "    sys.stdout.write(json.dumps({'number': int(num),"
        " 'sub_issues_summary': summ}))",
        "    sys.exit(0)",
        "if len(a) >= 2 and a[0] == 'issue' and a[1] == 'view':",
        "    num = a[2]",
        "    st = STATES.get(str(num), 'OPEN')",
        "    sys.stdout.write(json.dumps({'number': int(num), 'state': st}))",
        "    sys.exit(0)",
        "if len(a) >= 2 and a[0] == 'issue' and a[1] == 'close':",
        "    with open(CLOSE_LOG, 'a') as f:",
        "        f.write(' '.join(a) + '\\n')",
        "    sys.exit(0)",
        "sys.stderr.write('unexpected gh invocation: ' + ' '.join(a) + '\\n')",
        "sys.exit(3)",
        "",
    ]
    with open(shim, "w") as f:
        f.write("\n".join(py))
    os.chmod(shim, stat.S_IRWXU)


def _make_env(td, summaries, child_states):
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    close_log = os.path.join(td, "close.log")
    open(close_log, "w").close()
    _write_gh_shim(bin_dir, summaries, child_states, close_log)
    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return state_dir, close_log, env


def _closes(close_log):
    with open(close_log) as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def _closed_parents(close_log):
    """Return the set of parent numbers passed to `gh issue close`."""
    out = set()
    for ln in _closes(close_log):
        parts = ln.split()
        # issue close <n> ...
        if len(parts) >= 3 and parts[0] == "issue" and parts[1] == "close":
            out.add(parts[2])
    return out


def _run(env):
    return subprocess.run(
        [sys.executable, SCRIPT], env=env, capture_output=True, text=True)


# --- --help smoke ----------------------------------------------------------
proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                      capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"help: 'usage' missing; stdout={proc.stdout!r}")
else:
    ok("help: usage text present")


# --- native rollup complete -> parent closed + key dropped ----------------
with tempfile.TemporaryDirectory() as td:
    # Parent 677 native rollup shows 3/3 complete.
    summaries = {677: {"total": 3, "completed": 3}}
    state_dir, close_log, env = _make_env(td, summaries, {})
    _seed_state(state_dir, {"677": [679, 680, 681]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"native-complete: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("native-complete: exit 0")
    if "677" not in _closed_parents(close_log):
        fail(f"native-complete: parent 677 not closed; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("native-complete: parent 677 closed via gh issue close")
    if not any("--reason completed" in ln for ln in _closes(close_log)):
        fail(f"native-complete: close not --reason completed; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("native-complete: close used --reason completed")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if "677" in dp:
        fail(f"native-complete: parent key 677 not removed; dp={dp!r}")
    else:
        ok("native-complete: parent key removed from decomposition_parents")


# --- native rollup incomplete -> parent untouched, key retained -----------
with tempfile.TemporaryDirectory() as td:
    # Parent 677 native rollup shows 2/3 complete -> NOT closeable.
    summaries = {677: {"total": 3, "completed": 2}}
    state_dir, close_log, env = _make_env(td, summaries, {})
    _seed_state(state_dir, {"677": [679, 680, 681]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"native-incomplete: exit {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("native-incomplete: exit 0")
    if "677" in _closed_parents(close_log):
        fail(f"native-incomplete: parent 677 closed despite incomplete rollup; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("native-incomplete: parent 677 NOT closed (rollup completed<total)")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if dp.get("677") != [679, 680, 681]:
        fail(f"native-incomplete: parent key 677 not retained intact; dp={dp!r}")
    else:
        ok("native-incomplete: parent key retained")


# --- mixed: one complete rollup, one incomplete ---------------------------
with tempfile.TemporaryDirectory() as td:
    summaries = {677: {"total": 2, "completed": 2},   # closeable
                 530: {"total": 2, "completed": 1}}   # NOT closeable
    state_dir, close_log, env = _make_env(td, summaries, {})
    _seed_state(state_dir, {"677": [679, 680], "530": [531, 532]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"mixed: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("mixed: exit 0")
    closed = _closed_parents(close_log)
    if "677" not in closed:
        fail(f"mixed: closeable parent 677 not closed; closes={closed!r}")
    else:
        ok("mixed: closeable parent 677 closed")
    if "530" in closed:
        fail(f"mixed: parent 530 closed despite incomplete rollup; "
             f"closes={closed!r}")
    else:
        ok("mixed: parent 530 NOT closed")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if "677" in dp or dp.get("530") != [531, 532]:
        fail(f"mixed: state not updated correctly; dp={dp!r}")
    else:
        ok("mixed: 677 removed, 530 retained")


# --- legacy coexistence: no native sub-issues -> hand-rolled fallback ------
with tempfile.TemporaryDirectory() as td:
    # Parent 935 has NO native sub-issues yet (total==0) but a live legacy
    # decomposition_parents entry. Its recorded children are all CLOSED, so the
    # legacy hand-rolled per-child check must close it.
    summaries = {}  # 935 absent -> total 0
    child_states = {940: "CLOSED", 941: "CLOSED", 942: "CLOSED"}
    state_dir, close_log, env = _make_env(td, summaries, child_states)
    _seed_state(state_dir, {"935": [940, 941, 942]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"legacy-allclosed: exit {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("legacy-allclosed: exit 0")
    if "935" not in _closed_parents(close_log):
        fail(f"legacy-allclosed: parent 935 not closed via legacy fallback; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("legacy-allclosed: parent 935 closed via legacy hand-rolled check "
           "(coexistence path)")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if "935" in dp:
        fail(f"legacy-allclosed: parent key 935 not removed; dp={dp!r}")
    else:
        ok("legacy-allclosed: parent key 935 removed")


# --- legacy coexistence: no native sub-issues, one child OPEN -> untouched -
with tempfile.TemporaryDirectory() as td:
    summaries = {}  # 935 absent -> total 0
    child_states = {940: "CLOSED", 941: "OPEN", 942: "CLOSED"}
    state_dir, close_log, env = _make_env(td, summaries, child_states)
    _seed_state(state_dir, {"935": [940, 941, 942]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"legacy-oneopen: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("legacy-oneopen: exit 0")
    if "935" in _closed_parents(close_log):
        fail(f"legacy-oneopen: parent 935 closed despite an open child; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("legacy-oneopen: parent 935 NOT closed (legacy fallback, open child)")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if dp.get("935") != [940, 941, 942]:
        fail(f"legacy-oneopen: parent key 935 not retained intact; dp={dp!r}")
    else:
        ok("legacy-oneopen: parent key retained")


# --- empty map -> clean no-op ---------------------------------------------
with tempfile.TemporaryDirectory() as td:
    state_dir, close_log, env = _make_env(td, {}, {})
    _seed_state(state_dir, {})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"empty: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("empty: exit 0")
    if _closes(close_log):
        fail(f"empty: gh issue close invoked on empty map; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("empty: no gh issue close invoked (clean no-op)")


# --- absent decomposition_parents -> clean no-op --------------------------
with tempfile.TemporaryDirectory() as td:
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    close_log = os.path.join(td, "close.log")
    open(close_log, "w").close()
    _write_gh_shim(bin_dir, {}, {}, close_log)
    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    # state WITHOUT a decomposition_parents key
    state = {
        "schema_version": "1.4.0",
        "updated_at": "2026-06-04T00:00:00Z",
        "queue": [], "in_flight": [],
        "last_merged_sha": None, "last_tagged_version": None,
        "consecutive_failures": 0, "stop_requested": False,
        "restart_needed": None,
    }
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f)
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"absent: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("absent: exit 0 (no decomposition_parents key is a clean no-op)")
    if _closes(close_log):
        fail(f"absent: gh issue close invoked; closes={_closes(close_log)!r}")
    else:
        ok("absent: no gh issue close invoked")


sys.exit(FAIL)
