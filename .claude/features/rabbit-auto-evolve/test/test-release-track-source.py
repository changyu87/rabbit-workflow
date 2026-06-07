#!/usr/bin/env python3
"""test-release-track-source.py — issue #927 (root CHANGELOG.md stale vs v9.x tags)

End-to-end check that rabbit-auto-evolve's spec records the deterministic
release-track decision that resolves #927.

Background (#927): the repo-root `CHANGELOG.md` is owned by rabbit-cage
(Inv 28/45) and maintained under the now-dead `release/1.x` install-branch
scheme — frozen at `release/1.12.0` (see rabbit-cage Inv 22g, which names "the
dead `release/*` branch channel (frozen at 1.12.0)" vs "the live dev-tag
release channel"). The LIVE release track is the `vX.Y.Z` git tags cut by this
feature's `release-bump.py` (Inv 7) plus the per-feature `docs/CHANGELOG.md`
files. Root `CHANGELOG.md` is OUT of this feature's writable scope
(`RABBIT_CAGE_OWNED_ROOT` in rabbit-cage's scope-guard does not include it, and
no rabbit-auto-evolve marker authorizes a repo-root write), so the honest
resolution is to DOCUMENT that the canonical machine-truth of the live release
track is the git tags + per-feature changelogs — never the dead-track root
`CHANGELOG.md` — and to flag the #924 install-summary source choice (a
rabbit-cage concern) for re-sourcing.

This test pins exactly that documented decision in this feature's spec, so the
spec cannot silently drift back to claiming root `CHANGELOG.md` tracks `v9.x`.

  t1  docs/spec.md exists and is non-empty.
  t2  a dedicated invariant records the release-track decision (located by its
      release-track content, since the strict housekeeping gate forbids bare
      `#N` issue tags in spec body prose).
  t3  the invariant records that the LIVE release track is the git tags
      (vX.Y.Z) cut by release-bump.py plus per-feature changelogs.
  t4  the invariant records that root CHANGELOG.md is NOT this feature's
      authority / is out of scope (the dead release/1.x track).

Run non-interactively. Exits non-zero on failure.

Version: 0.74.0
Owner: rabbit-workflow team
Deprecation criterion: when root CHANGELOG.md is retired or the #924 install
summary is re-sourced off the live git-tag release track, making the
separate-track distinction moot.
"""
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1
if not os.path.isfile(SPEC) or os.path.getsize(SPEC) == 0:
    ko("t1", f"missing or empty: {SPEC}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", "docs/spec.md exists and is non-empty")

with open(SPEC, encoding="utf-8") as f:
    text = f.read()

# Locate the invariant that owns the release-track decision. The strict
# housekeeping gate forbids bare `#N` issue tags in spec body prose, so the
# invariant is located by its DISTINCT release-track content: a numbered
# invariant whose body names release-bump.py AND the root CHANGELOG.md track.
inv_re = re.compile(
    r"^(\d+)\. \*\*.*?(?=^\d+\. \*\*|\Z)", re.MULTILINE | re.DOTALL
)
target = None
for m in inv_re.finditer(text):
    body = m.group(0)
    low_body = body.lower()
    if "release-bump.py" in body and "root `changelog.md`" in low_body \
            and "release/1." in low_body:
        target = body
        break

# t2
if target is None:
    ko("t2", "no invariant records the release-track decision "
             "(release-bump.py + root CHANGELOG.md release/1.x)")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t2", "an invariant records the release-track decision")

low = target.lower()

# t3: the live track is the vX.Y.Z git tags cut by release-bump.py + per-feature
# changelogs.
if "release-bump.py" in target and "tag" in low and (
    "per-feature" in low or "docs/changelog" in low
):
    ok("t3", "invariant names git tags (release-bump.py) + per-feature "
             "changelogs as the live release track")
else:
    ko("t3", "invariant does not record the live track = git tags "
             "(release-bump.py) + per-feature changelogs")

# t4: root CHANGELOG.md is NOT this feature's authority / out of scope / dead
# release/1.x track.
mentions_root = "root `changelog.md`" in low or "root changelog" in low
out_of_authority = (
    "out of scope" in low
    or ("not " in low and "authorit" in low)
    or "dead" in low
    or "rabbit-cage" in low
)
if mentions_root and out_of_authority:
    ok("t4", "invariant records root CHANGELOG.md is the dead/out-of-scope "
             "release/1.x track, not this feature's authority")
else:
    ko("t4", "invariant does not record root CHANGELOG.md as the "
             "dead/out-of-scope release/1.x track")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
