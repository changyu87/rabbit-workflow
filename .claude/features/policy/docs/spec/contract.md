# Policy Feature — Contract

**version:** 1.0.0
**owner:** rabbit-workflow team

---

## What This Feature Provides

Four canonical rule files, each at a stable path within this feature directory:

| File | Path |
|------|------|
| Philosophy | `.claude/features/policy/philosophy.md` |
| Spec rules | `.claude/features/policy/spec-rules.md` |
| Coding rules | `.claude/features/policy/coding-rules.md` |
| Workflow rules | `.claude/features/policy/workflow-rules.md` |

File contents are stable across minor version increments. Breaking content changes (section removal, renamed headings that tests grep for) trigger a major version bump and a coexistence window.

---

## What Consumers Read

Consumers reference files by the stable paths above. They read file content directly — no intermediary API, no generated output. The contract is the file path and the section headings within each file.

Consumers MUST NOT assume file encoding beyond UTF-8, or rely on line numbers. Grep on heading text is the stable access pattern.

---

## What This Feature Never Does

- Never modifies files outside `.claude/features/policy/`.
- Never generates output directly to callers (no scripts that emit policy text on demand — callers read the files).
- Never duplicates content from other features or maintains a mirror of another feature's state.
- Never takes a dependency on any other feature's internals — only on stable paths declared in their contracts.
