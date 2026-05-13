---
feature: rabbit-cage
version: 3.6.0
template_version: 2.0.0
---

# rabbit-cage — Contract

```json
{
  "provides": {
    "files": [".claude/commands", ".claude/hooks", ".claude/skills", ".claude/settings.json", ".claude/policy", ".claude/contract", "CLAUDE.md", "README.md", "install.sh"],
    "commands": [
      {"path": ".claude/commands/rabbit-config.md", "subcommands": ["prompt-threshold [value]"]}
    ],
    "scripts": [
      {"path": ".claude/features/rabbit-cage/scripts/new-feature.sh", "stdin": "none", "stdout": "scaffold path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/validate-all.sh", "stdin": "none", "stdout": "validation report", "exit": "0=all pass 1=failures"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project.sh", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/generate-claude-md.sh", "stdin": "none", "stdout": "CLAUDE.md content", "exit": "0=ok 1=error"},
      {"path": ".claude/features/rabbit-cage/scripts/generate-skills-dir.sh", "stdin": "none", "stdout": "status messages", "exit": "0=ok/up-to-date 1=drift-detected(check-mode)"}
    ],
    "schemas": [],
    "templates": [],
    "skills": []
  },
  "reads": {
    "files": [".claude/features/registry.json", "project-*/project-map.json", ".claude/features/contract/templates/", ".rabbit-scope-override", ".rabbit-scope-override-used"],
    "external": ["env-var:RABBIT_ROOT"]
  },
  "invokes": {
    "scripts": [
      ".claude/features/contract/scripts/relink.sh",
      {"path": ".claude/features/contract/scripts/dispatch-feature-edit.sh", "stdin": "feature-name task-description", "stdout": "agent prompt", "exit": "0=ok 1=not-found 2=usage"}
    ],
    "agents":   []
  },
  "manages": {
    "runtime_markers": [
      {"path": ".rabbit-scope-override", "writer": "human or Claude (after explicit in-conversation user approval via confirm-token flow)", "reader": "scope-guard.sh, sync-check.sh", "lifecycle": "human or Claude creates (after in-conversation approval); scope-guard.sh deletes on one-time consumption; persists for session mode", "gitignored": true},
      {"path": ".rabbit-scope-override-used", "writer": "scope-guard.sh", "reader": "sync-check.sh", "lifecycle": "created by scope-guard.sh on one-time consumption; deleted by sync-check.sh after one alert", "gitignored": true}
    ]
  },
  "never": [
    "writes .claude/settings.local.json except via the /rabbit-config command on explicit user request",
    "modifies files inside another feature's directory",
    "writes outside its declared scope without an active scope marker or scope-guard override",
    "exposes /rabbit-set-threshold (replaced by /rabbit-config prompt-threshold)"
  ]
}
```

## CLAUDE.md Drift-Check Behavior

`CLAUDE.md` at the repo root is a committed artifact produced by
`generate-claude-md.sh`. It is not gitignored.

On every Stop event, `sync-check.sh` computes the expected `CLAUDE.md`
content from the current policy source files and compares it byte-for-byte
against the committed `CLAUDE.md`. If they differ, the hook regenerates
`CLAUDE.md` in place and emits a deep-green `[rabbit]` `systemMessage`
indicating that the committed copy drifted from the policy sources and that
the human should commit the regenerated file. If the committed file is
absent, the hook treats it as the first-run scenario and creates it.

## generate-skills-dir.sh Behavior

`generate-skills-dir.sh` populates `.claude/skills/` by recursively copying
each registered feature's skill source directory using `cp -rp` (preserving
mode and timestamps). It does not create or follow symlinks for skill content.

`--check` mode compares the sha256 of every source `SKILL.md` directly
against the sha256 of the corresponding copy at
`.claude/skills/<name>/SKILL.md`. No baseline hash file is read or written;
the prior `.rbt-skills-hash` file and any associated `compute_hash` helper
are removed. Exit `1` indicates drift in check mode; exit `0` indicates
the copy tree matches source (or, in non-check mode, that the copy
operation completed successfully).
