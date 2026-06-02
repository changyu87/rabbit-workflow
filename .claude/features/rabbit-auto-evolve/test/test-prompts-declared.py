#!/usr/bin/env python3
"""test-prompts-declared.py — feature.json declares prompts + runtime +
surface.skills + manifest.publish_skill per spec Inv 11, Inv 12.

Also verifies:
- The passthrough prompt template exists at
  .claude/features/contract/templates/prompts/rabbit-auto-evolve.txt.
- The workspace-structure.json features.children entry for
  rabbit-auto-evolve exists.
"""

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
FEATURE_JSON = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-auto-evolve/feature.json")
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
    if p.get("inject") != ["philosophy", "spec-rules", "coding-rules"]:
        fail(f"prompts[rabbit-auto-evolve].inject != "
             f"['philosophy', 'spec-rules', 'coding-rules'] (got {p.get('inject')})")
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

    # configuration entry (Inv 11) — set-evolve-mode.py + restart_required
    cfg = manifest.get("configuration", [])
    ae = [c for c in cfg if c.get("id") == "auto-evolve"]
    if not ae:
        fail("configuration missing id=auto-evolve entry")
    entry = ae[0]
    if entry.get("restart_required") is not True:
        fail("configuration[auto-evolve].restart_required must be true")
    vals = entry.get("values", {})
    for v in ("on", "off"):
        if v not in vals:
            fail(f"configuration[auto-evolve].values missing '{v}'")
        if vals[v].get("api") != "run_feature_script":
            fail(f"configuration[auto-evolve].values.{v}.api must be run_feature_script")
        if vals[v].get("args", {}).get("script") != "scripts/set-evolve-mode.py":
            fail(f"configuration[auto-evolve].values.{v} script must be "
                 f"scripts/set-evolve-mode.py")
        if vals[v].get("args", {}).get("argv") != [v]:
            fail(f"configuration[auto-evolve].values.{v}.argv must be ['{v}']")

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

    print("PASS: test-prompts-declared.py")


if __name__ == "__main__":
    main()
