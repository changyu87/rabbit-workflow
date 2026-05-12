---
name: "{{skill_name}}"
description: "Use when {{trigger_condition}}. Also use when user says {{trigger_phrases}}. Do NOT use for {{anti_trigger}}."
version: 1.0.0
owner: "{{owner}}"
deprecation_criterion: "{{deprecation_criterion}}"
template_version: 1.0.0
---

> **rabbit-workflow skill (`{{owner}}`)** — use when {{trigger_condition}}; NOT for {{anti_trigger}}.

## Overview

{{skill_name}} provides {{summary_of_capability}}. All scripts live at `.claude/features/{{owner}}/scripts/` relative to the repo root.

---

## When to Use

| Signal | Use this skill? |
|--------|----------------|
| {{trigger_phrase_1}} | Yes |
| {{trigger_phrase_2}} | Yes |
| {{anti_trigger_phrase_1}} | No |
| {{anti_trigger_phrase_2}} | No |

---

## Steps / Instructions

1. {{step_1}}
2. {{step_2}}
3. {{step_3}}

---

## Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| {{mistake_1}} | {{correction_1}} |
| {{mistake_2}} | {{correction_2}} |

---

## Red Flags

- {{red_flag_1}}
- {{red_flag_2}}
