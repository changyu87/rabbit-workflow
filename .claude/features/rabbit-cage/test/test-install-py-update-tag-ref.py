#!/usr/bin/env python3
"""test-install-py-update-tag-ref.py — e2e: install.main(--update --version <tag>)
fetches the latest TAG, not a frozen branch (#508).

The release model is now tags + GitHub Releases (#499): releases are cut as
`vX.Y.Z` tags. The update-check banner (contract check_release_update)
recommends `python3 .rabbit/install.py --update`, and the survivor command
must be able to acquire a tag-shaped ref. This test pins that install.py's
`--update` path is tag-agnostic:

  t1: `--update --version v1.0.7` forwards the tag ref verbatim to
      fetch_upstream (no branch coercion). _main_with_args is stubbed so the
      test exercises only the ref-resolution + fetch wiring without needing a
      full MVP source-closure copy.
  t2: fetch_upstream builds the GitHub archive URL for a tag ref, which is
      the identical archive endpoint used for branches
      (https://github.com/<repo>/archive/<tag>.tar.gz). Proves the existing
      fetch path already downloads tag tarballs with no code change.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

FAIL = 0


def fail(msg: str) -> None:
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg: str) -> None:
    print(f"PASS: {msg}")


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_main(install_mod, argv: list[str]) -> int:
    buf = io.StringIO()
    saved = sys.argv
    sys.argv = argv
    try:
        with redirect_stdout(buf):
            return install_mod.main()
    finally:
        sys.argv = saved


install = _load_install()

# t1: --update --version v1.0.7 forwards the tag ref verbatim to fetch_upstream.
#     Stub _main_with_args so we exercise only main()'s ref-resolution + fetch.
with tempfile.TemporaryDirectory() as td:
    target = Path(td) / "rabbit"
    target.mkdir()
    (target / ".claude").mkdir()
    (target / ".version").write_text("v1.0.6\n")

    calls: list[tuple[str, str]] = []

    def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
        calls.append((repo, ref))
        return Path(dest)

    with mock.patch.object(install, "fetch_upstream", side_effect=fake_fetch), \
            mock.patch.object(install, "_main_with_args", return_value=0):
        rc = _run_main(
            install,
            ["install.py", "--update", "--target", str(target), "--version", "v1.0.7"],
        )

    if rc != 0:
        fail(f"t1: --update --version v1.0.7 must succeed; got rc={rc}")
    elif len(calls) != 1:
        fail(f"t1: fetch_upstream must fire once; got {len(calls)}: {calls!r}")
    elif calls[0][1] != "v1.0.7":
        fail(f"t1: tag ref must flow through verbatim; got ref={calls[0][1]!r}")
    else:
        ok("t1: --update --version v1.0.7 forwards tag ref verbatim to fetch_upstream")

# t2: fetch_upstream builds the archive URL for a tag ref (same endpoint as a
#     branch ref) — proves the existing fetch path downloads tag tarballs.
captured: dict[str, str] = {}


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _fake_urlopen(url, *a, **k):
    captured["url"] = url
    import tarfile

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="rabbit-workflow-v1.0.7/.version")
        data = b"v1.0.7\n"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    raw.seek(0)
    return _FakeResp(raw.read())


with tempfile.TemporaryDirectory() as td:
    dest = Path(td)
    with mock.patch.object(install.urllib.request, "urlopen", _fake_urlopen):
        extracted = install.fetch_upstream("changyu87/rabbit-workflow", "v1.0.7", dest)
    expected = "https://github.com/changyu87/rabbit-workflow/archive/v1.0.7.tar.gz"
    if captured.get("url") != expected:
        fail(f"t2: tag archive URL mismatch; got {captured.get('url')!r}, want {expected!r}")
    elif extracted.name != "rabbit-workflow-v1.0.7":
        fail(f"t2: extracted dir mismatch; got {extracted.name!r}")
    else:
        ok("t2: fetch_upstream downloads tag tarball via the archive endpoint")


if FAIL:
    print("test-install-py-update-tag-ref: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-install-py-update-tag-ref: all checks passed.")
