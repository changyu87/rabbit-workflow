#!/usr/bin/env python3
"""test-prompts-declared.py — feature.json declares prompts + runtime +
surface.skills + manifest.publish_skill per spec Inv 11, Inv 12.

Also verifies:
- The passthrough prompt template exists at
  .claude/features/contract/templates/prompts/rabbit-auto-evolve.txt.
- The workspace-structure.json features.children entry for
  rabbit-auto-evolve exists.
- Inv 12 (fix #364): prompts[0].inject entries are full repo-relative
  paths to existing files; bare names (no '/') are FORBIDDEN because
  the prompt dispatcher does not resolve them.
- Inv 10 (fix #364): SKILL.md frontmatter MUST NOT pin a `model:` key —
  the default session model handles dispatch.
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
FEATURE_JSON = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-auto-evolve/feature.json")
SKILL_MD = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md")
PROMPT_TMPL = os.path.join(
    REPO_ROOT,
    ".claude/features/contract/templates/prompts/rabbit-auto-evolve.txt",
)
WORKSPACE = os.path.join(
    REPO_ROOT, ".claude/features/contract/workspace-structure.json")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    with open(FEATURE_JSON) as f:
        manifest = json.load(f)

    # surface.skills
    skills = manifest.get("surface", {}).get("skills", [])
    if "rabbit-auto-evolve" not in skills:
        fail(f"surface.skills missing rabbit-auto-evolve; got {skills}")

    # manifest publish_skill entry
    mfst = manifest.get("manifest", [])
    pub = [e for e in mfst if e.get("api") == "publish_skill"
           and e.get("args", {}).get("source", "").endswith(
               "skills/rabbit-auto-evolve/SKILL.md")]
    if not pub:
        fail("manifest missing publish_skill for skills/rabbit-auto-evolve/SKILL.md")

    # prompts entry (Inv 12)
    prompts = manifest.get("prompts", [])
    matching = [p for p in prompts if p.get("id") == "rabbit-auto-evolve"]
    if not matching:
        fail("prompts array missing id=rabbit-auto-evolve")
    p = matching[0]
    if p.get("kind") != "skill":
        fail(f"prompts[rabbit-auto-evolve].kind != 'skill' (got {p.get('kind')})")
    # Inv 12 (fix #364): inject entries are full repo-relative paths to
    # existing files; bare names (no '/') are FORBIDDEN.
    inject = p.get("inject")
    if not isinstance(inject, list) or not inject:
        fail(f"prompts[rabbit-auto-evolve].inject must be non-empty list "
             f"(got {inject!r})")
    for entry in inject:
        if not isinstance(entry, str):
            fail(f"prompts[rabbit-auto-evolve].inject entry not a string: "
                 f"{entry!r}")
        if "/" not in entry:
            fail(f"prompts[rabbit-auto-evolve].inject entry is a bare name "
                 f"(no '/'): {entry!r}; Inv 12 forbids bare names — use full "
                 f"repo-relative paths like '.claude/features/policy/<name>.md'")
        if not entry.startswith(".claude/features/policy/"):
            fail(f"prompts[rabbit-auto-evolve].inject entry must start with "
                 f"'.claude/features/policy/' (got {entry!r})")
        abs_path = os.path.join(REPO_ROOT, entry)
        if not os.path.isfile(abs_path):
            fail(f"prompts[rabbit-auto-evolve].inject entry does not exist "
                 f"on disk: {entry!r} (resolved to {abs_path})")
    if p.get("slots") != ["args"]:
        fail(f"prompts[rabbit-auto-evolve].slots != ['args'] (got {p.get('slots')})")

    # runtime SessionStart / Stop entries
    rt = manifest.get("runtime", {})
    ss = rt.get("SessionStart", [])
    if not any(e.get("api") == "emit_auto_evolve_banner" for e in ss):
        fail(f"runtime.SessionStart missing emit_auto_evolve_banner; got {ss}")
    stop = rt.get("Stop", [])
    if not any(e.get("api") == "emit_auto_evolve_stop_line" for e in stop):
        fail(f"runtime.Stop missing emit_auto_evolve_stop_line; got {stop}")

    # configuration (Inv 11) — MUST be empty or absent. Activation surface
    # lives on the rabbit-auto-evolve SKILL (on/off subcommands), NOT on
    # /rabbit-config.
    cfg = manifest.get("configuration", [])
    if cfg:
        ae = [c for c in cfg if c.get("id") == "auto-evolve"]
        if ae:
            fail("configuration must NOT contain id=auto-evolve entry "
                 "(Inv 11: activation surface moved to /rabbit-auto-evolve on|off)")
        # Any other entries are also unexpected — feature has no configurables.
        ids = [c.get("id") for c in cfg]
        fail(f"configuration array must be empty (got entries: {ids})")

    # passthrough template exists
    if not os.path.isfile(PROMPT_TMPL):
        fail(f"passthrough template missing: {PROMPT_TMPL}")

    # workspace-structure.json has the new child entry
    with open(WORKSPACE) as f:
        ws = json.load(f)
    feats_node = next(
        (n for n in ws.get("nodes", []) if n.get("name") == "features"), None)
    if feats_node is None:
        fail("workspace-structure.json missing features node")
    names = [c.get("name") for c in feats_node.get("children", [])]
    if "rabbit-auto-evolve" not in names:
        fail(f"workspace-structure.json features.children missing rabbit-auto-evolve; got {names}")

    # Inv 10 (fix #364): SKILL.md frontmatter MUST NOT pin a `model:` key.
    with open(SKILL_MD) as f:
        skill_text = f.read()
    m = re.search(r"(?ms)\A---\s*\n(.*?)\n---\s*\n", skill_text)
    if not m:
        fail(f"SKILL.md missing YAML frontmatter: {SKILL_MD}")
    fm_text = m.group(1)
    for line in fm_text.splitlines():
        key_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:", line)
        if key_match and key_match.group(1) == "model":
            fail(f"SKILL.md frontmatter MUST NOT pin a 'model:' key "
                 f"(Inv 10 — default session model handles dispatch); "
                 f"found line: {line!r}")

    print("PASS: test-prompts-declared.py")


if __name__ == "__main__":
    main()
