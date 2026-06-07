#!/usr/bin/env python3
"""test-check-preconditions.py — spec Inv 21 (added v0.7.3 for issue #375).

`scripts/check-preconditions.py` owns the three `start` preconditions.
Emits structured JSON on stdout with `{all_pass, checks: [{id, ok, detail}]}`.
Exit code is ALWAYS 0 — the verdict lives in `all_pass`, not in the exit code.
This is critical because the SKILL.md `start` section MUST NOT use bare
`ls .rabbit-auto-evolve-*` patterns, which emit stderr noise on fresh clones
where the markers legitimately do not yet exist.

Three stable check IDs (callers may rely on presence and order):
  - active-marker      (.rabbit-auto-evolve-active)
  - approval-bypass    (.rabbit-human-approval-bypass)
  - bypass-permissions (.claude/settings.local.json
                        permissions.defaultMode == "bypassPermissions")

The script honors RABBIT_AUTO_EVOLVE_REPO_ROOT for test isolation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "check-preconditions.py"

EXPECTED_IDS = ["active-marker", "approval-bypass", "bypass-permissions"]


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


def _run(repo_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


def _seed_active(td: Path) -> None:
    (td / ".rabbit-auto-evolve-active").write_text("session")


def _seed_approval_bypass(td: Path) -> None:
    (td / ".rabbit-human-approval-bypass").write_text("session")


def _seed_tdd_autonomous(td: Path) -> None:
    # Issue #336 Phase 1: the new bypass marker name. The reader must
    # accept this in place of the legacy .rabbit-human-approval-bypass.
    (td / ".rabbit-tdd-autonomous").write_text("session")


def _seed_bypass_permissions(td: Path) -> None:
    settings_dir = td / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.local.json"
    settings_path.write_text(
        json.dumps({"permissions": {"defaultMode": "bypassPermissions"}})
    )


print("test-check-preconditions.py")

# --- t1: script exists on disk ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")

# --- t2: --help smoke test ---
if SCRIPT.is_file():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        fail_t("help", f"--help exit {r.returncode}; stderr={r.stderr!r}")
    elif "usage" not in r.stdout.lower():
        fail_t("help", f"--help output lacks usage text: {r.stdout!r}")
    else:
        ok("help", "--help exits 0 with usage text")

# --- t3: all-fail scenario (clean tempdir, no markers, no settings file) ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "all-fail/exit",
                f"expected exit 0 always; got {r.returncode}; "
                f"stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("all-fail/json", f"stdout is not JSON: {e}; stdout={r.stdout!r}")
                report = None
            if report is not None:
                if report.get("all_pass") is not False:
                    fail_t(
                        "all-fail/all_pass",
                        f"expected all_pass=false, got {report.get('all_pass')!r}",
                    )
                else:
                    ok("all-fail/all_pass", "all_pass=false when all missing")
                checks = report.get("checks", [])
                ids = [c.get("id") for c in checks]
                if ids != EXPECTED_IDS:
                    fail_t(
                        "all-fail/ids",
                        f"check ids/order mismatch: expected {EXPECTED_IDS}, "
                        f"got {ids}",
                    )
                else:
                    ok("all-fail/ids", f"check ids present in order: {ids}")
                # All three should be ok=false in the all-fail scenario.
                bad_ok = [c for c in checks if c.get("ok") is not False]
                if bad_ok:
                    fail_t(
                        "all-fail/per-check-ok",
                        f"some checks reported ok != false: {bad_ok}",
                    )
                else:
                    ok(
                        "all-fail/per-check-ok",
                        "all three checks report ok=false",
                    )
                # Each failing check must carry a non-empty detail string.
                empty_details = [c for c in checks if not c.get("detail")]
                if empty_details:
                    fail_t(
                        "all-fail/details",
                        f"some failing checks have empty detail: {empty_details}",
                    )
                else:
                    ok("all-fail/details", "all failing checks carry detail strings")

# --- t4: all-pass scenario ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _seed_active(td_path)
        _seed_approval_bypass(td_path)
        _seed_bypass_permissions(td_path)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "all-pass/exit",
                f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("all-pass/json", f"stdout is not JSON: {e}")
                report = None
            if report is not None:
                if report.get("all_pass") is not True:
                    fail_t(
                        "all-pass/all_pass",
                        f"expected all_pass=true, got {report.get('all_pass')!r}",
                    )
                else:
                    ok("all-pass/all_pass", "all_pass=true when all present")
                checks = report.get("checks", [])
                bad = [c for c in checks if c.get("ok") is not True]
                if bad:
                    fail_t(
                        "all-pass/per-check-ok",
                        f"some checks not ok=true: {bad}",
                    )
                else:
                    ok("all-pass/per-check-ok", "all three checks report ok=true")

# --- t5: partial scenario (active marker present, neither bypass marker set) ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _seed_active(td_path)
        # leave both bypass markers and bypass-permissions absent
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "partial/exit",
                f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("partial/json", f"stdout is not JSON: {e}")
                report = None
            if report is not None:
                if report.get("all_pass") is not False:
                    fail_t(
                        "partial/all_pass",
                        f"expected all_pass=false, got {report.get('all_pass')!r}",
                    )
                else:
                    ok("partial/all_pass", "all_pass=false on partial activation")
                checks = {c.get("id"): c for c in report.get("checks", [])}
                active = checks.get("active-marker", {})
                approval = checks.get("approval-bypass", {})
                bypass = checks.get("bypass-permissions", {})
                if active.get("ok") is not True:
                    fail_t(
                        "partial/active-ok",
                        f"active-marker should be ok=true when present, "
                        f"got {active!r}",
                    )
                else:
                    ok("partial/active-ok", "active-marker ok=true")
                if approval.get("ok") is not False:
                    fail_t(
                        "partial/approval-not-ok",
                        f"approval-bypass should be ok=false when absent, "
                        f"got {approval!r}",
                    )
                else:
                    ok("partial/approval-not-ok", "approval-bypass ok=false")
                if bypass.get("ok") is not False:
                    fail_t(
                        "partial/bypass-not-ok",
                        f"bypass-permissions should be ok=false when settings "
                        f"missing, got {bypass!r}",
                    )
                else:
                    ok(
                        "partial/bypass-not-ok",
                        "bypass-permissions ok=false when settings absent",
                    )

# --- t6: malformed settings.local.json -> bypass-permissions ok=false, exit 0 ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _seed_active(td_path)
        _seed_approval_bypass(td_path)
        # settings file present but not valid JSON
        (td_path / ".claude").mkdir()
        (td_path / ".claude" / "settings.local.json").write_text("not json {{{")
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "malformed-settings/exit",
                f"expected exit 0 even with malformed settings; "
                f"got {r.returncode}; stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("malformed-settings/json", f"stdout not JSON: {e}")
                report = None
            if report is not None:
                checks = {c.get("id"): c for c in report.get("checks", [])}
                if checks.get("bypass-permissions", {}).get("ok") is not False:
                    fail_t(
                        "malformed-settings/bypass",
                        f"expected bypass-permissions ok=false on malformed "
                        f"settings, got {checks.get('bypass-permissions')!r}",
                    )
                else:
                    ok(
                        "malformed-settings/bypass",
                        "malformed settings gracefully reports ok=false",
                    )

# --- t7: dual-read — new .rabbit-tdd-autonomous marker alone satisfies
#         approval-bypass (issue #336 Phase 1 future state) ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _seed_active(td_path)
        _seed_tdd_autonomous(td_path)  # new name only, no legacy marker
        _seed_bypass_permissions(td_path)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "tdd-autonomous/exit",
                f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("tdd-autonomous/json", f"stdout not JSON: {e}")
                report = None
            if report is not None:
                checks = {c.get("id"): c for c in report.get("checks", [])}
                approval = checks.get("approval-bypass", {})
                if approval.get("ok") is not True:
                    fail_t(
                        "tdd-autonomous/approval-ok",
                        f"approval-bypass should be ok=true when "
                        f".rabbit-tdd-autonomous present, got {approval!r}",
                    )
                else:
                    ok(
                        "tdd-autonomous/approval-ok",
                        ".rabbit-tdd-autonomous alone satisfies approval-bypass",
                    )
                if report.get("all_pass") is not True:
                    fail_t(
                        "tdd-autonomous/all_pass",
                        f"expected all_pass=true with new marker, "
                        f"got {report.get('all_pass')!r}",
                    )
                else:
                    ok(
                        "tdd-autonomous/all_pass",
                        "all_pass=true when activated via new bypass marker",
                    )

# --- t8: dual-read — both bypass markers present satisfies approval-bypass
#         (issue #336 Phase 1 coexistence window) ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _seed_active(td_path)
        _seed_approval_bypass(td_path)  # legacy name
        _seed_tdd_autonomous(td_path)  # new name
        _seed_bypass_permissions(td_path)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "both-markers/exit",
                f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("both-markers/json", f"stdout not JSON: {e}")
                report = None
            if report is not None:
                checks = {c.get("id"): c for c in report.get("checks", [])}
                approval = checks.get("approval-bypass", {})
                if approval.get("ok") is not True:
                    fail_t(
                        "both-markers/approval-ok",
                        f"approval-bypass should be ok=true when both markers "
                        f"present, got {approval!r}",
                    )
                else:
                    ok(
                        "both-markers/approval-ok",
                        "both bypass markers present → approval-bypass ok=true",
                    )

# --- t9: legacy .rabbit-human-approval-bypass still satisfies approval-bypass
#         (issue #336 Phase 1 live state must keep working) ---
if SCRIPT.is_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _seed_active(td_path)
        _seed_approval_bypass(td_path)  # legacy name only
        _seed_bypass_permissions(td_path)
        r = _run(td_path)
        if r.returncode != 0:
            fail_t(
                "legacy-marker/exit",
                f"expected exit 0; got {r.returncode}; stderr={r.stderr!r}",
            )
        else:
            try:
                report = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                fail_t("legacy-marker/json", f"stdout not JSON: {e}")
                report = None
            if report is not None:
                checks = {c.get("id"): c for c in report.get("checks", [])}
                approval = checks.get("approval-bypass", {})
                if approval.get("ok") is not True:
                    fail_t(
                        "legacy-marker/approval-ok",
                        f"approval-bypass should be ok=true when legacy "
                        f".rabbit-human-approval-bypass present, got {approval!r}",
                    )
                else:
                    ok(
                        "legacy-marker/approval-ok",
                        "legacy .rabbit-human-approval-bypass still satisfies "
                        "approval-bypass",
                    )

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
