---
description: Set the auto-refresh threshold (prompts between policy re-injections). Writes to .claude/settings.local.json. Takes effect next session.
allowed-tools: Bash
---

Setting auto-refresh threshold to $ARGUMENTS prompts.

!`THRESHOLD="$ARGUMENTS" python3 -c "
import json, os, pathlib, sys
val = os.environ['THRESHOLD'].strip()
if not val.isdigit() or int(val) < 1:
    print('Error: argument must be a positive integer (e.g. /rabbit-set-threshold 15)', file=sys.stderr)
    sys.exit(1)
p = pathlib.Path('.claude/settings.local.json')
cfg = json.loads(p.read_text()) if p.exists() else {}
cfg.setdefault('env', {})['RBT_REFRESH_EVERY'] = val
p.write_text(json.dumps(cfg, indent=2) + '\n')
print('Written to .claude/settings.local.json')
"`

Threshold set to $ARGUMENTS prompts. Takes effect on next session start.
