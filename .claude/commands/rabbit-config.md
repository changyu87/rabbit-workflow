---
description: Configure rabbit-workflow settings. Subcommands: prompt-threshold [value] — set or restore the auto-refresh threshold.
allowed-tools: Bash
---

Configuring rabbit-workflow: $ARGUMENTS

!`ARGUMENTS="$ARGUMENTS" python3 -c "
import json, os, pathlib, sys

args = os.environ.get('ARGUMENTS', '').split()

USAGE = 'Usage: /rabbit-config prompt-threshold [value]\n  prompt-threshold <N>  — set auto-refresh threshold to N (positive integer)\n  prompt-threshold      — remove threshold override, restoring default'

if not args:
    print(USAGE)
    sys.exit(1)

subcmd = args[0]

if subcmd == 'prompt-threshold':
    val = args[1] if len(args) > 1 else ''
    p = pathlib.Path('.claude/settings.local.json')
    cfg = json.loads(p.read_text()) if p.exists() else {}

    if not val:
        # Restore default: remove RABBIT_REFRESH_EVERY key
        cfg.get('env', {}).pop('RABBIT_REFRESH_EVERY', None)
        if 'env' in cfg and not cfg['env']:
            del cfg['env']
        p.write_text(json.dumps(cfg, indent=2) + '\n')
        print('Threshold removed from .claude/settings.local.json — default from settings.json is restored.')
        print('Takes effect on next session start.')
    else:
        if not val.isdigit() or int(val) < 1:
            print('Error: value must be a positive integer (e.g. /rabbit-config prompt-threshold 15)', file=sys.stderr)
            sys.exit(1)
        cfg.setdefault('env', {})['RABBIT_REFRESH_EVERY'] = val
        p.write_text(json.dumps(cfg, indent=2) + '\n')
        print(f'Threshold set to {val} prompts in .claude/settings.local.json.')
        print('Takes effect on next session start.')
else:
    print(f'Unknown subcommand: {subcmd!r}', file=sys.stderr)
    print(USAGE, file=sys.stderr)
    sys.exit(1)
"`
