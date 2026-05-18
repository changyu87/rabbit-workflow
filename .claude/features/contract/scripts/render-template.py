#!/usr/bin/env python3
"""render-template.py — substitute {{key}} placeholders in a template file.

Usage (invoked by render-template.sh):
  python3 render-template.py <template-path> <output-path> [key=value ...]

key=value pairs are accepted directly; values are treated as plain strings.
Unresolved placeholders are left as-is.

Exit:
  0 success
  1 template file missing or parse error
  2 invocation error

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when template rendering is provided by a native feature mechanism.
"""

import sys


def main():
    if len(sys.argv) < 3:
        print("usage: render-template.py <template-path> <output-path> [key=value ...]", file=sys.stderr)
        sys.exit(2)

    template_path = sys.argv[1]
    output_path = sys.argv[2]
    pairs = sys.argv[3:]

    subs = {}
    for pair in pairs:
        if '=' not in pair:
            print(f"ERROR: invalid key=value pair: {pair!r}", file=sys.stderr)
            sys.exit(2)
        key, _, val = pair.partition('=')
        subs[key] = val

    try:
        with open(template_path) as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    for key, val in subs.items():
        content = content.replace("{{" + key + "}}", val)

    with open(output_path, "w") as f:
        f.write(content)

    print(f"Rendered: {template_path} -> {output_path}")


if __name__ == '__main__':
    main()
