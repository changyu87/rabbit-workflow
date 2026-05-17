---
feature: rabbit-feature-scope
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When feature-scope resolution is automated natively by the dispatch infrastructure.
status: active
---

# rabbit-feature-scope — Spec

## Purpose

Provides `resolve-scope.py`, which builds a prompt for a default-model Agent to map
a natural-language request to the list of rabbit features whose files the request
will modify. Makes no assumptions about callers or use cases.

## Surface

- `.claude/features/rabbit-feature-scope/scripts/resolve-scope.py`
- `.claude/features/rabbit-feature-scope/scripts/format-feature-context.py`
- `.claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md`

## Invariants

1. `resolve-scope.py` emits a prompt to stdout only; it never calls Agent itself.
2. The dispatched Agent uses the default model — no Opus override.
3. The script uses `find-feature.py list-json` for feature enumeration; never reads `registry.json`.
4. Agent response JSON schema: `{"features": ["name1", ...], "rationale": "one sentence"}`.
5. `resolve-scope.py` is executable.
6. An empty `features` list `[]` is a valid response (no features touched).
7. `resolve-scope.py` contains no inline `python3 -c` calls or python3 heredocs; all Python logic is in `format-feature-context.py`.
8. `format-feature-context.py` reads JSON from stdin and writes the formatted feature context to stdout; it is invoked as `python3 format-feature-context.py`.
9. `SKILL.md` Usage section MUST present shell-executable commands and Claude
   tool-invocation pseudo-code in **separate code blocks with distinct fence
   labels**. The shell command that generates the prompt (`PROMPT=$(...)`) is
   in a ```bash``` fence; the `Agent(...)` tool invocation is in a non-shell
   fence (e.g., ```text```) and is preceded by a sentence explicitly stating
   that it is a Claude tool call and must NOT be shell-executed. Mixing the
   two in one bash fence is prohibited because agents reading the SKILL
   literally will attempt to shell-exec the `Agent(...)` call, which always
   fails (tcsh raises `no matches found: Agent(prompt: ...)`, bash returns
   command-not-found).
