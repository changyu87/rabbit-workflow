---
description: Configure rabbit-workflow settings. Subcommands: prompt-threshold [value]; allowed-tools [add|remove <tool>]; bash-allow [add|remove <command>].
allowed-tools: Bash
---

Configuring rabbit-workflow: $ARGUMENTS

!`ARGUMENTS="$ARGUMENTS" python3 -c "
import json, os, pathlib, re, sys

args = os.environ.get('ARGUMENTS', '').split()

USAGE = '''Usage:
  /rabbit-config prompt-threshold [value]
      prompt-threshold <N>           set auto-refresh threshold to N (positive integer)
      prompt-threshold               remove threshold override, restoring default
  /rabbit-config allowed-tools [add|remove <tool>]
      allowed-tools add <tool>       add <tool> to permissions.allow in settings.json
      allowed-tools remove <tool>    remove <tool> from permissions.allow
      allowed-tools                  list current entries (excluding Bash(...) entries managed by bash-allow)
  /rabbit-config bash-allow [add|remove <command>]
      bash-allow add <command>       add Bash(<command>:*) to permissions.allow in settings.json
      bash-allow remove <command>    remove Bash(<command>:*) from permissions.allow
      bash-allow                     list current bash-allow commands (inner names)'''

if not args:
    print(USAGE)
    sys.exit(1)

subcmd = args[0]

def load_local():
    p = pathlib.Path('.claude/settings.local.json')
    return p, (json.loads(p.read_text()) if p.exists() else {})

def load_settings():
    p = pathlib.Path('.claude/settings.json')
    return p, (json.loads(p.read_text()) if p.exists() else {})

def write_json(p, cfg):
    p.write_text(json.dumps(cfg, indent=2) + '\n')

def perm_allow(cfg):
    return cfg.setdefault('permissions', {}).setdefault('allow', [])

if subcmd == 'prompt-threshold':
    val = args[1] if len(args) > 1 else ''
    p, cfg = load_local()

    if not val:
        cfg.get('env', {}).pop('RABBIT_REFRESH_EVERY', None)
        if 'env' in cfg and not cfg['env']:
            del cfg['env']
        write_json(p, cfg)
        print('Threshold removed from .claude/settings.local.json - default from settings.json is restored.')
        print('Takes effect on next session start.')
    else:
        if not val.isdigit() or int(val) < 1:
            print('Error: value must be a positive integer (e.g. /rabbit-config prompt-threshold 15)', file=sys.stderr)
            sys.exit(1)
        cfg.setdefault('env', {})['RABBIT_REFRESH_EVERY'] = val
        write_json(p, cfg)
        print(f'Threshold set to {val} prompts in .claude/settings.local.json.')
        print('Takes effect on next session start.')

elif subcmd == 'allowed-tools':
    action = args[1] if len(args) > 1 else ''
    value  = args[2] if len(args) > 2 else ''

    if action == '':
        # List current non-Bash entries
        p, cfg = load_settings()
        for entry in cfg.get('permissions', {}).get('allow', []):
            if not entry.startswith('Bash('):
                print(entry)
        sys.exit(0)

    if action not in ('add', 'remove'):
        print(f'Error: unknown action {action!r} for allowed-tools (expected add or remove)', file=sys.stderr)
        sys.exit(1)
    if not value:
        print(f'Error: allowed-tools {action} requires a <tool> value', file=sys.stderr)
        sys.exit(1)
    if value.startswith('Bash('):
        print(f'Error: {value!r} looks like a Bash rule; use /rabbit-config bash-allow instead', file=sys.stderr)
        sys.exit(1)

    p, cfg = load_settings()
    allow = perm_allow(cfg)
    if action == 'add':
        if value in allow:
            print(f'Already present: {value}')
        else:
            allow.append(value)
            write_json(p, cfg)
            print(f'Added {value} to .claude/settings.json')
    else:  # remove
        if value in allow:
            allow.remove(value)
            write_json(p, cfg)
            print(f'Removed {value} from .claude/settings.json')
        else:
            print(f'Not present: {value}')

elif subcmd == 'bash-allow':
    action = args[1] if len(args) > 1 else ''
    value  = args[2] if len(args) > 2 else ''

    if action == '':
        # List current Bash(<cmd>:*) inner names
        p, cfg = load_settings()
        pat = re.compile(r'^Bash\(([^():\s]+):\*\)$')
        for entry in cfg.get('permissions', {}).get('allow', []):
            m = pat.match(entry)
            if m:
                print(m.group(1))
        sys.exit(0)

    if action not in ('add', 'remove'):
        print(f'Error: unknown action {action!r} for bash-allow (expected add or remove)', file=sys.stderr)
        sys.exit(1)
    if not value:
        print(f'Error: bash-allow {action} requires a <command> value', file=sys.stderr)
        sys.exit(1)
    if re.search(r'[()\s:]', value):
        print(f'Error: bash-allow command must not contain parens, colons, or whitespace; got {value!r}', file=sys.stderr)
        sys.exit(1)

    entry = f'Bash({value}:*)'
    p, cfg = load_settings()
    allow = perm_allow(cfg)
    if action == 'add':
        if entry in allow:
            print(f'Already present: {entry}')
        else:
            allow.append(entry)
            write_json(p, cfg)
            print(f'Added {entry} to .claude/settings.json')
    else:  # remove
        if entry in allow:
            allow.remove(entry)
            write_json(p, cfg)
            print(f'Removed {entry} from .claude/settings.json')
        else:
            print(f'Not present: {entry}')

else:
    print(f'Unknown subcommand: {subcmd!r}', file=sys.stderr)
    print(USAGE, file=sys.stderr)
    sys.exit(1)
"`
