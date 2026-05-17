---
name: repo-permissions
description: Lock or unlock owner write permission on archive/ and test/ directories. Use when setting up a fresh clone (lock), or when you need to edit archived items or test fixtures (unlock). Invoke as Skill("repo-permissions", args: "lock") or Skill("repo-permissions", args: "unlock"). Also triggers on phrases like "make archive read-only", "lock the test directory", "unlock archive for editing", "set up repo permissions after clone".
---

# repo-permissions

Manage write permissions on `archive/` and `test/` directories using `repo-permissions.py`.

## Usage

**Lock** (read-only — run after git clone):
```bash
python3 .claude/features/rabbit-cage/scripts/repo-permissions.py lock
```

**Unlock** (writable — run before editing archived items or test fixtures):
```bash
python3 .claude/features/rabbit-cage/scripts/repo-permissions.py unlock
```

Both commands honor `ARCHIVE_DIR` and `TEST_DIR` environment variables (defaults: `archive/`, `test/`). Symlinks are always skipped.

## When to lock
- After a fresh `git clone`
- After finishing edits to archived items or test fixtures

## When to unlock
- Before editing anything in `archive/` or `test/`
- Remember to lock again when done
