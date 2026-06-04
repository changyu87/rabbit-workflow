#!/usr/bin/env python3
"""test-republish-feature.py — rabbit-auto-evolve Inv 55 (issue #562).

End-to-end tests for `scripts/republish-feature.py`, the deterministic
dispatcher step that refreshes a feature's deployed copies from source by
reading the feature's `feature.json` `manifest` and INVOKING the
contract-owned `contract.lib.publish.<api>` for every `publish_*` entry.

Each test builds a TEMP FIXTURE repo (never the live workspace): a
`.claude/features/<feat>/feature.json` with a `manifest`, a source
`skills/<feat>/SKILL.md`, and (optionally) a deployed
`.claude/skills/<feat>/SKILL.md`. The fixture also vendors the real
`contract` feature's `lib/` (publish + checks) so the script resolves
`contract.lib.publish` exactly as it does in the live tree. The script is
asserted to:

  - make a stale deployed copy MATCH source and report it as changed,
  - be a clean no-op (changed:false) when the deployed copy already matches,
  - be a clean no-op for a feature with no manifest / no publish entries,
  - emit a JSON summary on stdout in every case.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "republish-feature.py"
# The real contract feature the script invokes; its lib/ (publish + checks) and
# schemas/ (checks.py sources the runtime API enum from runtime.schema.json at
# import time, Inv 41) are vendored into each fixture so the import path mirrors
# the live tree (features/contract/{lib,schemas}/).
REAL_CONTRACT = FEATURE_DIR.parent / "contract"
REAL_CONTRACT_LIB = REAL_CONTRACT / "lib"
REAL_CONTRACT_SCHEMAS = REAL_CONTRACT / "schemas"

pass_n = 0
fail_n = 0


def ok(t: str, msg: str) -> None:
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t: str, msg: str) -> None:
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


def _make_fixture(repo: Path, feat: str, *, manifest, source_skill_text,
                  deployed_skill_text=None) -> None:
    """Build a fixture repo with the contract lib vendored and a feature whose
    SKILL.md source (and optional deployed copy) are seeded."""
    # Vendor the real contract lib + schemas so the script resolves
    # contract.lib.publish (lib.checks loads runtime.schema.json at import).
    contract_dst = repo / ".claude" / "features" / "contract"
    contract_dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REAL_CONTRACT_LIB, contract_dst / "lib")
    shutil.copytree(REAL_CONTRACT_SCHEMAS, contract_dst / "schemas")

    feat_dir = repo / ".claude" / "features" / feat
    feat_dir.mkdir(parents=True, exist_ok=True)
    fj = {"name": feat, "version": "1.0.0"}
    if manifest is not None:
        fj["manifest"] = manifest
    (feat_dir / "feature.json").write_text(json.dumps(fj, indent=2) + "\n")

    if source_skill_text is not None:
        src = feat_dir / "skills" / feat / "SKILL.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(source_skill_text)

    if deployed_skill_text is not None:
        dep = repo / ".claude" / "skills" / feat / "SKILL.md"
        dep.parent.mkdir(parents=True, exist_ok=True)
        dep.write_text(deployed_skill_text)


def _run(repo: Path, feat: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), feat, "--repo-root", str(repo)],
        capture_output=True, text=True, cwd=str(repo),
    )


def _manifest_for(feat: str):
    return [{"api": "publish_skill",
             "args": {"source": f"skills/{feat}/SKILL.md"}}]


print("test-republish-feature.py")

# --- t0: script exists ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")

# --- t1: a stale deployed SKILL.md is made to match source and reported ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    feat = "rabbit-demo"
    _make_fixture(
        repo, feat,
        manifest=_manifest_for(feat),
        source_skill_text="SOURCE v2 content\n",
        deployed_skill_text="OLD deployed v1 content\n",
    )
    r = _run(repo, feat)
    dep = repo / ".claude" / "skills" / feat / "SKILL.md"
    src = repo / ".claude" / "features" / feat / "skills" / feat / "SKILL.md"
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("stale/match", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("stale/match", f"stdout not JSON: {r.stdout!r}")
    elif dep.read_text() != src.read_text():
        fail_t("stale/match", "deployed copy does NOT match source after run")
    elif obj.get("status") != "ok":
        fail_t("stale/match", f"status not ok: {obj!r}")
    elif not obj.get("published"):
        fail_t("stale/match", f"published list empty: {obj!r}")
    elif not any(p.get("changed") is True for p in obj["published"]):
        fail_t("stale/match", f"no entry reported changed: {obj['published']!r}")
    else:
        ok("stale/match",
           "stale deployed SKILL.md republished to match source, reported changed")

# --- t2: a deployed copy already matching source is a clean no-op ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    feat = "rabbit-demo"
    same = "IDENTICAL content\n"
    _make_fixture(
        repo, feat,
        manifest=_manifest_for(feat),
        source_skill_text=same,
        deployed_skill_text=same,
    )
    r = _run(repo, feat)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("noop/match", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("noop/match", f"stdout not JSON: {r.stdout!r}")
    elif obj.get("status") != "ok":
        fail_t("noop/match", f"status not ok: {obj!r}")
    elif not obj.get("published"):
        fail_t("noop/match", f"published list empty (entry expected): {obj!r}")
    elif any(p.get("changed") is True for p in obj["published"]):
        fail_t("noop/match", f"an entry wrongly reported changed: {obj['published']!r}")
    else:
        ok("noop/match",
           "matching deployed copy is a no-op (changed:false), JSON emitted")

# --- t3: a feature with NO manifest is a clean no-op ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    feat = "rabbit-nomanifest"
    _make_fixture(
        repo, feat,
        manifest=None,
        source_skill_text="SOURCE\n",
    )
    r = _run(repo, feat)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("noop/no-manifest", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("noop/no-manifest", f"stdout not JSON: {r.stdout!r}")
    elif obj.get("status") != "ok":
        fail_t("noop/no-manifest", f"status not ok: {obj!r}")
    elif obj.get("published"):
        fail_t("noop/no-manifest",
               f"published list non-empty on no-manifest: {obj.get('published')!r}")
    else:
        ok("noop/no-manifest",
           "feature with no manifest -> clean no-op, empty published list")

# --- t4: a feature with an EMPTY manifest is a clean no-op ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    feat = "rabbit-emptymanifest"
    _make_fixture(
        repo, feat,
        manifest=[],
        source_skill_text="SOURCE\n",
    )
    r = _run(repo, feat)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("noop/empty-manifest", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("noop/empty-manifest", f"stdout not JSON: {r.stdout!r}")
    elif obj.get("published"):
        fail_t("noop/empty-manifest",
               f"published list non-empty on empty manifest: {obj.get('published')!r}")
    else:
        ok("noop/empty-manifest", "empty manifest -> clean no-op")

# --- t5: deployed copy ABSENT is created (first publish) and reported changed ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    feat = "rabbit-fresh"
    _make_fixture(
        repo, feat,
        manifest=_manifest_for(feat),
        source_skill_text="FRESH SOURCE\n",
        deployed_skill_text=None,
    )
    dep = repo / ".claude" / "skills" / feat / "SKILL.md"
    r = _run(repo, feat)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("fresh/create", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("fresh/create", f"stdout not JSON: {r.stdout!r}")
    elif not dep.is_file():
        fail_t("fresh/create", "deployed copy was not created")
    elif dep.read_text() != "FRESH SOURCE\n":
        fail_t("fresh/create", "deployed copy content mismatch")
    elif not any(p.get("changed") is True for p in obj.get("published", [])):
        fail_t("fresh/create", f"first publish not reported changed: {obj!r}")
    else:
        ok("fresh/create",
           "absent deployed copy created from source, reported changed")

# --- t6: idempotent second run after t5-style publish is a no-op ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    feat = "rabbit-idem"
    _make_fixture(
        repo, feat,
        manifest=_manifest_for(feat),
        source_skill_text="IDEM SOURCE\n",
        deployed_skill_text=None,
    )
    r1 = _run(repo, feat)
    r2 = _run(repo, feat)
    try:
        obj2 = json.loads(r2.stdout)
    except json.JSONDecodeError:
        obj2 = None
    if r1.returncode != 0 or r2.returncode != 0:
        fail_t("idempotent", f"exit r1={r1.returncode} r2={r2.returncode}")
    elif obj2 is None:
        fail_t("idempotent", f"second run stdout not JSON: {r2.stdout!r}")
    elif any(p.get("changed") is True for p in obj2.get("published", [])):
        fail_t("idempotent", f"second run reported a change: {obj2!r}")
    else:
        ok("idempotent", "second run after publish is a no-op (changed:false)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
