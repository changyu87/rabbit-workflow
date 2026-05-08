---
description: Re-inject the rabbit-workflow policy files into context and reset the auto-refresh counter.
allowed-tools: Bash
---

Refreshing rabbit-workflow policy files.

!`echo 0 > .rwf-counter`

!`for p in $(grep -oE '^@[^[:space:]]+' CLAUDE.md | sed 's/^@//'); do echo "=== $p ==="; cat "$p"; echo; done`

In one sentence, confirm which files were refreshed.
