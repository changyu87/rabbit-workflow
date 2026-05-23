#!/usr/bin/env python3
"""test-dispatcher-lib.py — unit tests for hooks/_dispatcher_lib.py.

Covers:
- enumerate_features: alphabetical iteration, retired-skip, malformed-skip
- dispatch_event: invokes the right runtime API with the right args,
  collects results across features in alphabetical-then-declaration order
- render_emission: partitions print/inject/error/ok; returns None when
  there is nothing to surface
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB_PATH = REPO / ".claude/features/rabbit-cage/hooks/_dispatcher_lib.py"


def _load_lib():
    spec = importlib.util.spec_from_file_location("_dispatcher_lib", LIB_PATH)
    mod = importlib.util.module_from_spec(spec)
    # _dispatcher_lib needs contract on sys.path to import runtime; ensure it
    # finds the real contract feature.
    contract_dir = str(REPO / ".claude/features/contract")
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    spec.loader.exec_module(mod)
    return mod


def _write_feature(root: Path, name: str, payload: dict) -> Path:
    fdir = root / ".claude/features" / name
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "feature.json").write_text(json.dumps(payload))
    return fdir


def test_enumerate_alpha_and_skips():
    lib = _load_lib()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_feature(root, "bbb", {"name": "bbb"})
        _write_feature(root, "aaa", {"name": "aaa"})
        _write_feature(root, "ccc", {"name": "ccc", "status": "retired"})
        # malformed JSON
        bad = root / ".claude/features/zzz_bad"
        bad.mkdir(parents=True)
        (bad / "feature.json").write_text("{not json")
        # directory without feature.json
        nopj = root / ".claude/features/empty"
        nopj.mkdir(parents=True)

        names = [n for n, _, _ in lib.enumerate_features(str(root))]
        assert names == ["aaa", "bbb"], f"expected [aaa,bbb], got {names}"
    print("PASS test_enumerate_alpha_and_skips")


def test_dispatch_event_invokes_runtime_api():
    lib = _load_lib()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        marker = root / ".my-marker"
        marker.write_text("active")
        _write_feature(root, "f1", {
            "name": "f1",
            "runtime": {
                "Stop": [
                    {"api": "check_marker_alert",
                     "args": {"path": ".my-marker", "content": None,
                              "alert": {"text": "ALERT-X", "icon": "warn", "color": "red"}}},
                ]
            },
        })

        results = lib.dispatch_event("Stop", str(root))
        assert len(results) == 1, f"expected 1 result, got {results}"
        r = results[0]
        assert r["type"] == "print" and r["text"] == "ALERT-X", r

        # absent marker -> ok_result
        marker.unlink()
        results = lib.dispatch_event("Stop", str(root))
        assert len(results) == 1 and results[0]["type"] == "ok", results
    print("PASS test_dispatch_event_invokes_runtime_api")


def test_dispatch_event_ordering_across_features():
    lib = _load_lib()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        m1 = root / ".m1"; m1.write_text("x")
        m2 = root / ".m2"; m2.write_text("x")
        _write_feature(root, "bb", {
            "name": "bb",
            "runtime": {"Stop": [
                {"api": "check_marker_alert",
                 "args": {"path": ".m2", "content": None,
                          "alert": {"text": "BB", "icon": "i", "color": "red"}}},
            ]},
        })
        _write_feature(root, "aa", {
            "name": "aa",
            "runtime": {"Stop": [
                {"api": "check_marker_alert",
                 "args": {"path": ".m1", "content": None,
                          "alert": {"text": "AA1", "icon": "i", "color": "red"}}},
                {"api": "check_marker_alert",
                 "args": {"path": ".m1", "content": None,
                          "alert": {"text": "AA2", "icon": "i", "color": "red"}}},
            ]},
        })

        results = lib.dispatch_event("Stop", str(root))
        texts = [r.get("text") for r in results if r["type"] == "print"]
        assert texts == ["AA1", "AA2", "BB"], texts
    print("PASS test_dispatch_event_ordering_across_features")


def test_dispatch_event_unknown_api_emits_error():
    lib = _load_lib()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_feature(root, "f", {
            "name": "f",
            "runtime": {"Stop": [
                {"api": "no_such_api", "args": {}},
            ]},
        })
        results = lib.dispatch_event("Stop", str(root))
        assert len(results) == 1 and results[0]["type"] == "error", results
    print("PASS test_dispatch_event_unknown_api_emits_error")


def test_render_emission_partitions():
    lib = _load_lib()
    payloads = [
        {"type": "print", "text": "T1", "icon": "i1", "color": "red"},
        {"type": "inject", "content": "INJECTED_A\n"},
        {"type": "ok"},
        {"type": "error", "message": "boom"},
        {"type": "print", "text": "T2", "icon": "i2", "color": "green"},
        {"type": "inject", "content": "INJECTED_B"},
    ]
    out = lib.render_emission(payloads)
    assert out is not None
    assert "T1" in out["systemMessage"] and "T2" in out["systemMessage"], out
    assert out["systemMessage"].startswith("\n"), "rabbit_block leading newline missing"
    assert out["additionalContext"] == "INJECTED_A\nINJECTED_B", out
    print("PASS test_render_emission_partitions")


def test_render_emission_empty_returns_none():
    lib = _load_lib()
    assert lib.render_emission([]) is None
    assert lib.render_emission([{"type": "ok"}, {"type": "ok"}]) is None
    assert lib.render_emission([{"type": "error", "message": "x"}]) is None
    print("PASS test_render_emission_empty_returns_none")


def test_render_emission_banner_type_produces_banner_line():
    """banner-type results render via rabbit_print (banner format), not subline."""
    lib = _load_lib()
    payloads = [
        {"type": "banner", "message_id": "welcome"},
    ]
    out = lib.render_emission(payloads)
    assert out is not None, "expected non-None emission for banner result"
    sm = out.get("systemMessage", "")
    # The 'welcome' banner contains the bar character '━━━' from the banner format
    assert "━━━" in sm, f"expected banner bar in systemMessage, got: {sm!r}"
    # The brand prefix must be present
    assert "[🐇 rabbit 🐇]" in sm, f"brand prefix missing from systemMessage: {sm!r}"
    print("PASS test_render_emission_banner_type_produces_banner_line")


def test_render_emission_subline_type_renders_as_subline():
    """subline-type results render via rabbit_subline (no bar decoration)."""
    lib = _load_lib()
    payloads = [
        {"type": "subline", "text": "philosophy.md    — machine-first", "color": "green"},
    ]
    out = lib.render_emission(payloads)
    assert out is not None
    sm = out.get("systemMessage", "")
    # sublines do NOT carry the ━━━ bar decoration
    assert "━━━" not in sm, f"subline should not have bar: {sm!r}"
    assert "philosophy.md" in sm, f"text missing from subline: {sm!r}"
    assert "[🐇 rabbit 🐇]" in sm, f"brand prefix missing: {sm!r}"
    print("PASS test_render_emission_subline_type_renders_as_subline")


def test_render_emission_banner_and_sublines_order():
    """banner + sublines appear in order in the systemMessage."""
    lib = _load_lib()
    payloads = [
        {"type": "banner", "message_id": "welcome"},
        {"type": "subline", "text": "LINE-A", "color": "green"},
        {"type": "subline", "text": "LINE-B", "color": "green"},
        {"type": "inject", "content": "POLICY"},
    ]
    out = lib.render_emission(payloads)
    assert out is not None
    sm = out["systemMessage"]
    pos_banner = sm.find("━━━")
    pos_a = sm.find("LINE-A")
    pos_b = sm.find("LINE-B")
    assert pos_banner != -1, "banner bar not found"
    assert pos_a != -1 and pos_b != -1, "subline texts not found"
    assert pos_banner < pos_a < pos_b, f"ordering wrong: banner={pos_banner} a={pos_a} b={pos_b}"
    assert out["additionalContext"] == "POLICY"
    print("PASS test_render_emission_banner_and_sublines_order")


def main() -> int:
    test_enumerate_alpha_and_skips()
    test_dispatch_event_invokes_runtime_api()
    test_dispatch_event_ordering_across_features()
    test_dispatch_event_unknown_api_emits_error()
    test_render_emission_partitions()
    test_render_emission_empty_returns_none()
    test_render_emission_banner_type_produces_banner_line()
    test_render_emission_subline_type_renders_as_subline()
    test_render_emission_banner_and_sublines_order()
    return 0


if __name__ == "__main__":
    sys.exit(main())
