#!/usr/bin/env python3
"""BACKLOG-19 / Inv 77: hooks consume the shared rabbit_print renderer.

Asserts that the three rabbit-cage hook source files contain NO inline
ANSI escape sequences, NO literal `[rabbit]` brand prefix, and NO `━━━`
bar character outside of comments / docstrings / contract-import statements.
Also asserts each hook imports `rabbit_print` and `rabbit_subline` from the
shared renderer module.
"""
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
import subprocess
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

HOOKS = [
    os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py"),
    os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py"),
    os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/refresh.py"),
]

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def strip_string_and_comment_safe_check(source: str, needle: str) -> int:
    """Return count of occurrences in non-comment, non-docstring code lines.

    We are strict: ANY occurrence outside of leading comment lines (#) and
    triple-quoted module docstring counts. We use a simple heuristic: drop
    lines that begin with `#` (ignoring leading whitespace) and drop the
    module docstring. This is sufficient because rabbit-cage hooks have a
    module docstring near the top and otherwise plain code.
    """
    # Remove module docstring (triple-quoted string at the top of file, after shebang/comment lines)
    # Simple approach: find first triple-quoted block and remove it.
    src = source
    m = re.search(r'^\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*\n', src, re.MULTILINE)
    if m and m.start() < 500:
        # Replace it only if it's near the top (module docstring).
        src = src[:m.start()] + src[m.end():]

    # Drop comment-only lines for the search.
    kept = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        kept.append(line)
    body = "\n".join(kept)
    return body.count(needle)


print("test-RABBIT-CAGE-BACKLOG-19-renderer-adoption.py")
print()

for hook_path in HOOKS:
    name = os.path.basename(hook_path)
    print(f"=== {name} ===")
    if not os.path.isfile(hook_path):
        fail_t(f"{name} does not exist")
        continue

    with open(hook_path) as f:
        src = f.read()

    # (a) No direct ANSI escape sequences in code: \x1b or \033 literal
    n_x1b = strip_string_and_comment_safe_check(src, "\\x1b")
    n_033 = strip_string_and_comment_safe_check(src, "\\033")
    if n_x1b == 0 and n_033 == 0:
        ok(f"{name} contains no inline \\x1b or \\033 ANSI escapes in code")
    else:
        fail_t(f"{name} contains inline ANSI escapes (\\x1b={n_x1b}, \\033={n_033})")

    # (b) No literal `[rabbit]` brand
    n_rab = strip_string_and_comment_safe_check(src, "[rabbit]")
    if n_rab == 0:
        ok(f"{name} contains no literal [rabbit] brand in code")
    else:
        fail_t(f"{name} contains {n_rab} literal [rabbit] brand strings in code")

    # (c) No literal `━━━` bar
    n_bar = strip_string_and_comment_safe_check(src, "━━━")
    if n_bar == 0:
        ok(f"{name} contains no literal ━━━ bar in code")
    else:
        fail_t(f"{name} contains {n_bar} literal ━━━ bars in code")

    # (d) Imports rabbit_print and rabbit_subline
    if "from rabbit_print import rabbit_print, rabbit_subline" in src:
        ok(f"{name} imports `rabbit_print, rabbit_subline` from rabbit_print")
    else:
        fail_t(f"{name} does NOT import `from rabbit_print import rabbit_print, rabbit_subline`")
    print()

print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
