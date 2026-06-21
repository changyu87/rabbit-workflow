#!/usr/bin/env python3
"""test-measure-reduction.py — E2E for the deterministic measurement script.

Drives scripts/measure-reduction.py as a subprocess against fixture trees
built under tempfile.TemporaryDirectory(), so the test never depends on the
live repo's contents. Behaviours covered:

  t0: script exists and is executable.
  t1: `count` reports correct per-file line counts and a correct __total__.
  t2: `count` walks a directory recursively and skips a binary file.
  t3: `diff` of a BEFORE snapshot vs an AFTER snapshot where lines were
      REMOVED reports reduced=true and a negative total_delta.
  t4: `diff` of a reword (same total line count) reports reduced=false and
      total_delta == 0.
  t5: `diff` surfaces per_artifact before/after/delta and removed_paths.
  t6: invocation error (unknown subcommand / bad diff arity) exits 2.
  t7: `count --docs-only` over a feature dir restricts the walk to the doc
      surfaces a wave slims (docs/spec.md, docs/contract.md, skills/*/SKILL.md)
      and EXCLUDES test/ and docs/CHANGELOG.md, so when the wave slims docs
      but adds its mandated housekeeping test, the doc-scoped diff still
      reports reduced=true (the #1187 failure mode, fixed).

Non-interactive. Exits non-zero on failure.

Version: 0.2.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "measure-reduction.py")

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


def run(*args):
    return subprocess.run(
        ["python3", SCRIPT, *args], capture_output=True, text=True
    )


# t0
if not (os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK)):
    fail("t0", f"missing or non-executable: {SCRIPT}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "measure-reduction.py exists and is executable")

# t1: count per-file + total
with tempfile.TemporaryDirectory() as tmp:
    a = os.path.join(tmp, "a.txt")
    b = os.path.join(tmp, "b.txt")
    with open(a, "w") as f:
        f.write("one\ntwo\nthree\n")  # 3 lines
    with open(b, "w") as f:
        f.write("x\ny")  # 2 lines, no trailing newline
    r = run("count", a, b)
    if r.returncode != 0:
        fail("t1", f"count exited {r.returncode}; stderr={r.stderr}")
    else:
        data = json.loads(r.stdout)
        if (data.get(os.path.normpath(a)) == 3
                and data.get(os.path.normpath(b)) == 2
                and data.get("__total__") == 5):
            ok("t1", "count reports correct per-file counts and total")
        else:
            fail("t1", f"unexpected counts: {data}")

# t2: directory walk + binary skip
with tempfile.TemporaryDirectory() as tmp:
    sub = os.path.join(tmp, "docs")
    os.makedirs(sub)
    with open(os.path.join(sub, "spec.md"), "w") as f:
        f.write("l1\nl2\nl3\nl4\n")  # 4 lines
    with open(os.path.join(tmp, "binary.bin"), "wb") as f:
        f.write(b"\x00\x01\x02\x00")  # NUL -> skipped
    r = run("count", tmp)
    data = json.loads(r.stdout)
    keys = [k for k in data if k != "__total__"]
    has_md = any(k.endswith(os.path.join("docs", "spec.md")) for k in keys)
    has_bin = any(k.endswith("binary.bin") for k in keys)
    if r.returncode == 0 and has_md and not has_bin and data["__total__"] == 4:
        ok("t2", "count walks dir recursively and skips binary files")
    else:
        fail("t2", f"unexpected: rc={r.returncode}; data={data}")


def write_snapshot(path, mapping):
    with open(path, "w") as f:
        json.dump(mapping, f)


# t3: reduction -> reduced true, negative delta
with tempfile.TemporaryDirectory() as tmp:
    before = os.path.join(tmp, "before.json")
    after = os.path.join(tmp, "after.json")
    write_snapshot(before, {"spec.md": 100, "contract.md": 50, "__total__": 150})
    write_snapshot(after, {"spec.md": 70, "contract.md": 50, "__total__": 120})
    r = run("diff", before, after)
    d = json.loads(r.stdout)
    if r.returncode == 0 and d["reduced"] is True and d["total_delta"] == -30:
        ok("t3", "diff reports reduced=true with negative total_delta")
    else:
        fail("t3", f"unexpected: rc={r.returncode}; d={d}")

# t4: reword (same totals) -> reduced false, delta 0
with tempfile.TemporaryDirectory() as tmp:
    before = os.path.join(tmp, "before.json")
    after = os.path.join(tmp, "after.json")
    write_snapshot(before, {"spec.md": 100, "__total__": 100})
    write_snapshot(after, {"spec.md": 100, "__total__": 100})
    r = run("diff", before, after)
    d = json.loads(r.stdout)
    if r.returncode == 0 and d["reduced"] is False and d["total_delta"] == 0:
        ok("t4", "diff of a reword reports reduced=false, total_delta=0")
    else:
        fail("t4", f"unexpected: rc={r.returncode}; d={d}")

# t5: per_artifact + removed_paths
with tempfile.TemporaryDirectory() as tmp:
    before = os.path.join(tmp, "before.json")
    after = os.path.join(tmp, "after.json")
    write_snapshot(before, {"a": 10, "b": 5, "__total__": 15})
    write_snapshot(after, {"a": 4, "__total__": 4})  # b removed, a slimmed
    r = run("diff", before, after)
    d = json.loads(r.stdout)
    pa = d.get("per_artifact", {})
    if (d["reduced"] is True
            and pa.get("a", {}).get("delta") == -6
            and pa.get("b", {}).get("after") == 0
            and "b" in d.get("removed_paths", [])):
        ok("t5", "diff surfaces per_artifact deltas and removed_paths")
    else:
        fail("t5", f"unexpected: d={d}")

# t6: invocation errors exit 2
r1 = run("bogus")
r2 = run("diff", "only-one-arg.json")
if r1.returncode == 2 and r2.returncode == 2:
    ok("t6", "invocation errors exit 2")
else:
    fail("t6", f"expected exit 2 both; got {r1.returncode}, {r2.returncode}")

# t8: honest verdict — a no-change wave is an honest `no-op`, not a failure.
# A wave that removes lines reports verdict `reduced`; a wave that changes
# nothing because nothing was dead reports verdict `no-op`. Reduction is
# REPORTED, never MANDATED, so an already-clean target passes honestly.
with tempfile.TemporaryDirectory() as tmp:
    before = os.path.join(tmp, "before.json")
    after_same = os.path.join(tmp, "after-same.json")
    after_less = os.path.join(tmp, "after-less.json")
    write_snapshot(before, {"spec.md": 100, "__total__": 100})
    write_snapshot(after_same, {"spec.md": 100, "__total__": 100})
    write_snapshot(after_less, {"spec.md": 70, "__total__": 70})
    d_same = json.loads(run("diff", before, after_same).stdout)
    d_less = json.loads(run("diff", before, after_less).stdout)
    if (d_same.get("verdict") == "no-op" and d_same.get("reduced") is False
            and d_less.get("verdict") == "reduced"
            and d_less.get("reduced") is True):
        ok("t8", "diff reports verdict no-op for a no-change wave and reduced "
                 "for a removal (honest already-clean outcome)")
    else:
        fail("t8", f"unexpected verdicts: same={d_same}; less={d_less}")


def write_feature_tree(root, spec_lines, contract_lines, skill_lines,
                       changelog_lines, test_lines, src_lines=0):
    """Build a minimal feature tree mirroring a consuming-project feature's
    layout. A non-zero src_lines writes a `src/<name>.py` source file so the
    code-dimension (`--code`) walk has something to count."""
    docs = os.path.join(root, "docs")
    skills = os.path.join(root, "skills", "demo")
    test = os.path.join(root, "test")
    for d in (docs, skills, test):
        os.makedirs(d)
    body = lambda n: "".join(f"l{i}\n" for i in range(n))
    with open(os.path.join(docs, "spec.md"), "w") as f:
        f.write(body(spec_lines))
    with open(os.path.join(docs, "contract.md"), "w") as f:
        f.write(body(contract_lines))
    with open(os.path.join(docs, "CHANGELOG.md"), "w") as f:
        f.write(body(changelog_lines))
    with open(os.path.join(skills, "SKILL.md"), "w") as f:
        f.write(body(skill_lines))
    with open(os.path.join(test, "test-demo.py"), "w") as f:
        f.write(body(test_lines))
    if src_lines:
        src = os.path.join(root, "src")
        os.makedirs(src, exist_ok=True)
        with open(os.path.join(src, "mod.py"), "w") as f:
            f.write(body(src_lines))


# t7: --docs-only scopes the walk to doc surfaces. The #1187 failure mode:
# docs shrink, but the wave adds its mandated housekeeping test under test/.
# A whole-tree count flips reduced->false; --docs-only stays reduced->true.
with tempfile.TemporaryDirectory() as tmp:
    feat = os.path.join(tmp, "demo")
    # BEFORE: spec 100, contract 50, skill 80, changelog 10, test 0
    write_feature_tree(feat, 100, 50, 80, 10, 0)
    rb_all = run("count", feat)
    rb_docs = run("count", "--docs-only", feat)
    before_all = os.path.join(tmp, "before-all.json")
    before_docs = os.path.join(tmp, "before-docs.json")
    with open(before_all, "w") as f:
        f.write(rb_all.stdout)
    with open(before_docs, "w") as f:
        f.write(rb_docs.stdout)

    # AFTER: docs slimmed (spec 100->70, contract 50->40, skill unchanged),
    # changelog GROWS (10->40), and the wave adds a 157-line test file.
    import shutil
    shutil.rmtree(feat)
    write_feature_tree(feat, 70, 40, 80, 40, 157)
    ra_all = run("count", feat)
    ra_docs = run("count", "--docs-only", feat)
    after_all = os.path.join(tmp, "after-all.json")
    after_docs = os.path.join(tmp, "after-docs.json")
    with open(after_all, "w") as f:
        f.write(ra_all.stdout)
    with open(after_docs, "w") as f:
        f.write(ra_docs.stdout)

    # docs-only count must exclude test/ and docs/CHANGELOG.md.
    docs_keys = [k for k in json.loads(rb_docs.stdout) if k != "__total__"]
    has_changelog = any(k.endswith("CHANGELOG.md") for k in docs_keys)
    has_test = any(os.sep + "test" + os.sep in k for k in docs_keys)
    has_spec = any(k.endswith(os.path.join("docs", "spec.md")) for k in docs_keys)
    has_contract = any(
        k.endswith(os.path.join("docs", "contract.md")) for k in docs_keys)
    has_skill = any(k.endswith("SKILL.md") for k in docs_keys)

    d_all = json.loads(run("diff", before_all, after_all).stdout)
    d_docs = json.loads(run("diff", before_docs, after_docs).stdout)

    if (rb_docs.returncode == 0 and ra_docs.returncode == 0
            and has_spec and has_contract and has_skill
            and not has_changelog and not has_test
            and d_all["reduced"] is False  # whole-tree: false (the bug)
            and d_docs["reduced"] is True   # doc-scoped: true (the fix)
            and d_docs["total_delta"] == -40):
        ok("t7", "count --docs-only scopes to doc surfaces; reduced=true "
                 "even when a test is added (#1187)")
    else:
        fail("t7", f"docs_keys={docs_keys}; d_all.reduced={d_all['reduced']}; "
                   f"d_docs={d_docs}")

# t9: --code scopes the walk to the feature's `src/` SOURCE files (the code
# dimension), counting `src/**/*.py` and EXCLUDING docs/, test/, and
# skills/ — symmetric to --docs-only for the doc dimension. Opt-in: the
# default whole-tree walk and --docs-only are unchanged.
with tempfile.TemporaryDirectory() as tmp:
    import shutil
    feat = os.path.join(tmp, "demo")
    # spec 100, contract 50, skill 80, changelog 10, test 30, src 60
    write_feature_tree(feat, 100, 50, 80, 10, 30, src_lines=60)
    rc_code = run("count", "--code", feat)
    code_data = json.loads(rc_code.stdout)
    code_keys = [k for k in code_data if k != "__total__"]
    only_src = code_keys and all(
        os.sep + "src" + os.sep in k and k.endswith(".py") for k in code_keys)
    excludes_docs = not any(
        os.sep + "docs" + os.sep in k for k in code_keys)
    excludes_test = not any(
        os.sep + "test" + os.sep in k for k in code_keys)

    # A code-dimension reduction is measured the same way: slim src 60->45.
    before_code = os.path.join(tmp, "before-code.json")
    with open(before_code, "w") as f:
        f.write(rc_code.stdout)
    shutil.rmtree(feat)
    write_feature_tree(feat, 100, 50, 80, 10, 30, src_lines=45)
    ra_code = run("count", "--code", feat)
    after_code = os.path.join(tmp, "after-code.json")
    with open(after_code, "w") as f:
        f.write(ra_code.stdout)
    d_code = json.loads(run("diff", before_code, after_code).stdout)

    if (rc_code.returncode == 0 and only_src and excludes_docs
            and excludes_test and code_data.get("__total__") == 60
            and d_code["reduced"] is True and d_code["total_delta"] == -15
            and d_code.get("verdict") == "reduced"):
        ok("t9", "count --code scopes to src/ source files; a src reduction "
                 "is measured the same way (reduced=true)")
    else:
        fail("t9", f"code_keys={code_keys}; total={code_data.get('__total__')}; "
                   f"d_code={d_code}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
