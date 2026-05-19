#!/usr/bin/env python3
"""rabbit-config — extensible configuration command for the rabbit workflow.

Subcommands:
  prompt-threshold [N]                 set/clear RABBIT_REFRESH_EVERY in settings.local.json
  allowed-tools [add|remove <tool>]    manage permissions.allow entries (non-Bash)
  bash-allow    [add|remove <command>] manage Bash(<command>:*) permissions.allow entries
  permissions    lock|unlock           delegate to repo-permissions.py
  human-approval [true|false]          manage Step 4 (HUMAN-APPROVAL) gate state
  bypass-permissions [true|false]      manage permissions.defaultMode in settings.local.json

All argv parsing comes from sys.argv[1:]; this script is the sole implementation
of /rabbit-config. There is no slash-command shim file (per spec Inv 25);
the rabbit-config skill is the sole entry point.
"""
import json
import pathlib
import re
import subprocess
import sys


USAGE = '''Usage:
  /rabbit-config prompt-threshold [value]
      prompt-threshold <N>           set auto-refresh threshold to N (positive integer)
      prompt-threshold               remove threshold override, restoring default
  /rabbit-config allowed-tools [add|remove <tool>]
      allowed-tools add <tool>       add <tool> to permissions.allow in settings.local.json
      allowed-tools remove <tool>    remove <tool> from permissions.allow
      allowed-tools                  list current entries (excluding Bash(...) entries managed by bash-allow)
  /rabbit-config bash-allow [add|remove <command>]
      bash-allow add <command>       add Bash(<command>:*) to permissions.allow in settings.local.json
      bash-allow remove <command>    remove Bash(<command>:*) from permissions.allow
      bash-allow                     list current bash-allow commands (inner names)
  /rabbit-config permissions lock|unlock
      lock     remove owner write permission from archive/ and test/ (run after git clone)
      unlock   restore owner write permission to archive/ and test/ (run before editing)
  /rabbit-config human-approval [true|false]
      human-approval false           write .rabbit-human-approval-bypass marker (bypass Step 4)
      human-approval true            remove the marker (Step 4 gate active — default)
      human-approval                 print current gate state: 'true' (active) or 'false' (bypassed)
  /rabbit-config bypass-permissions [true|false]
      bypass-permissions true        set permissions.defaultMode='bypassPermissions' in .claude/settings.local.json (per-user opt-in)
      bypass-permissions false       remove permissions.defaultMode from .claude/settings.local.json
      bypass-permissions             print current state: 'true' if defaultMode='bypassPermissions' in settings.local.json, else 'false' '''


def load_local():
    p = pathlib.Path('.claude/settings.local.json')
    return p, (json.loads(p.read_text()) if p.exists() else {})


def write_json(p, cfg):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + '\n')


def perm_allow(cfg):
    return cfg.setdefault('permissions', {}).setdefault('allow', [])


def cmd_prompt_threshold(args):
    val = args[0] if args else ''
    p, cfg = load_local()
    if not val:
        cfg.get('env', {}).pop('RABBIT_REFRESH_EVERY', None)
        if 'env' in cfg and not cfg['env']:
            del cfg['env']
        write_json(p, cfg)
        print('Threshold removed from .claude/settings.local.json - default from settings.json is restored.')
        print('Takes effect on next session start.')
        return 0
    if not val.isdigit() or int(val) < 1:
        print('Error: value must be a positive integer (e.g. /rabbit-config prompt-threshold 15)', file=sys.stderr)
        return 1
    cfg.setdefault('env', {})['RABBIT_REFRESH_EVERY'] = val
    write_json(p, cfg)
    print(f'Threshold set to {val} prompts in .claude/settings.local.json.')
    print('Takes effect on next session start.')
    return 0


def cmd_allowed_tools(args):
    action = args[0] if args else ''
    value = args[1] if len(args) > 1 else ''
    if action == '':
        p, cfg = load_local()
        for entry in cfg.get('permissions', {}).get('allow', []):
            if not entry.startswith('Bash('):
                print(entry)
        return 0
    if action not in ('add', 'remove'):
        print(f'Error: unknown action {action!r} for allowed-tools (expected add or remove)', file=sys.stderr)
        return 1
    if not value:
        print(f'Error: allowed-tools {action} requires a <tool> value', file=sys.stderr)
        return 1
    if value.startswith('Bash('):
        print(f'Error: {value!r} looks like a Bash rule; use /rabbit-config bash-allow instead', file=sys.stderr)
        return 1
    p, cfg = load_local()
    # BUG-66: avoid setdefault on the remove-of-absent path so we don't write
    # an empty {"permissions": {"allow": []}} back to disk.
    existing_allow = cfg.get('permissions', {}).get('allow', [])
    if action == 'add':
        allow = perm_allow(cfg)
        if value in allow:
            print(f'Already present: {value}')
        else:
            allow.append(value)
            write_json(p, cfg)
            print(f'Added {value} to .claude/settings.local.json')
    else:
        if value in existing_allow:
            allow = perm_allow(cfg)
            allow.remove(value)
            write_json(p, cfg)
            print(f'Removed {value} from .claude/settings.local.json')
        else:
            print(f'Not present: {value}')
    return 0


def cmd_bash_allow(args):
    action = args[0] if args else ''
    value = args[1] if len(args) > 1 else ''
    if action == '':
        p, cfg = load_local()
        pat = re.compile(r'^Bash\(([^():\s]+):\*\)$')
        for entry in cfg.get('permissions', {}).get('allow', []):
            m = pat.match(entry)
            if m:
                print(m.group(1))
        return 0
    if action not in ('add', 'remove'):
        print(f'Error: unknown action {action!r} for bash-allow (expected add or remove)', file=sys.stderr)
        return 1
    if not value:
        print(f'Error: bash-allow {action} requires a <command> value', file=sys.stderr)
        return 1
    if re.search(r'[()\s:]', value):
        print(f'Error: bash-allow command must not contain parens, colons, or whitespace; got {value!r}', file=sys.stderr)
        return 1
    entry = f'Bash({value}:*)'
    p, cfg = load_local()
    # BUG-66: avoid setdefault on the remove-of-absent path.
    existing_allow = cfg.get('permissions', {}).get('allow', [])
    if action == 'add':
        allow = perm_allow(cfg)
        if entry in allow:
            print(f'Already present: {entry}')
        else:
            allow.append(entry)
            write_json(p, cfg)
            print(f'Added {entry} to .claude/settings.local.json')
    else:
        if entry in existing_allow:
            allow = perm_allow(cfg)
            allow.remove(entry)
            write_json(p, cfg)
            print(f'Removed {entry} from .claude/settings.local.json')
        else:
            print(f'Not present: {entry}')
    return 0


def cmd_permissions(args):
    action = args[0] if args else ''
    if action not in ('lock', 'unlock'):
        print('Error: permissions requires lock or unlock', file=sys.stderr)
        return 1
    script = pathlib.Path('.claude/features/rabbit-cage/scripts/repo-permissions.py')
    result = subprocess.run([sys.executable, str(script), action])
    return result.returncode


def cmd_human_approval(args):
    action = args[0] if args else ''
    marker = pathlib.Path('.rabbit-human-approval-bypass')
    if action == '':
        # State query: 'true' = gate active (marker absent); 'false' = bypassed (marker present)
        print('false' if marker.exists() else 'true')
        return 0
    if action == 'false':
        if marker.exists():
            # Idempotent no-op: do not rewrite the marker file.
            print(
                f'Human-approval gate already BYPASSED (marker {marker} already present; no rewrite). '
                'Step 4 will be skipped for all dispatches until you run '
                '/rabbit-config human-approval true.'
            )
            return 0
        marker.write_text('session')
        print(
            f'Human-approval gate BYPASSED. Marker {marker} written. '
            'Step 4 will be skipped for all dispatches until you run '
            '/rabbit-config human-approval true.'
        )
        return 0
    if action == 'true':
        if marker.exists():
            marker.unlink()
            print(
                f'Human-approval gate ENABLED. Marker {marker} removed. '
                'Step 4 will wait for in-conversation approval on each dispatch.'
            )
        else:
            print(
                'Human-approval gate already ENABLED (no marker present). '
                'Step 4 will wait for in-conversation approval on each dispatch.'
            )
        return 0
    print(f'Error: unknown value {action!r} for human-approval (expected true, false, or no action)', file=sys.stderr)
    return 1


def cmd_bypass_permissions(args):
    action = args[0] if args else ''
    p, cfg = load_local()
    current = cfg.get('permissions', {}).get('defaultMode')
    if action == '':
        # State query: print 'true' if defaultMode == bypassPermissions, else 'false'.
        print('true' if current == 'bypassPermissions' else 'false')
        return 0
    if action == 'true':
        if current == 'bypassPermissions':
            # Idempotent no-op: do not rewrite the file.
            print(
                'Bypass permissions already ENABLED in .claude/settings.local.json. '
                '(file unchanged)'
            )
            return 0
        cfg.setdefault('permissions', {})['defaultMode'] = 'bypassPermissions'
        write_json(p, cfg)
        print(
            'Bypass permissions ENABLED in .claude/settings.local.json. '
            'Claude Code will skip native per-write prompts on next session start.'
        )
        return 0
    if action == 'false':
        if current is None:
            print(
                'Bypass permissions already DISABLED (key absent). (file unchanged)'
            )
            return 0
        del cfg['permissions']['defaultMode']
        if not cfg['permissions']:
            del cfg['permissions']
        write_json(p, cfg)
        print(
            'Bypass permissions DISABLED. permissions.defaultMode removed '
            'from .claude/settings.local.json. Claude Code will prompt for '
            'writes again on next session start.'
        )
        return 0
    print(f'Error: unknown value {action!r} for bypass-permissions (expected true, false, or no action)', file=sys.stderr)
    return 1


def main(argv):
    if not argv:
        print(USAGE)
        return 1
    subcmd = argv[0]
    rest = argv[1:]
    dispatch = {
        'prompt-threshold': cmd_prompt_threshold,
        'allowed-tools': cmd_allowed_tools,
        'bash-allow': cmd_bash_allow,
        'permissions': cmd_permissions,
        'human-approval': cmd_human_approval,
        'bypass-permissions': cmd_bypass_permissions,
    }
    handler = dispatch.get(subcmd)
    if handler is None:
        print(f'Unknown subcommand: {subcmd!r}', file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 1
    return handler(rest)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
