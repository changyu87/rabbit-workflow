#!/usr/bin/env python3
"""BACKLOG-19 / Inv 87, 88 (v3.10.0): hooks consume the named-wrapper API
+ rabbit_block assembler from rabbit_print.

Asserts that the three rabbit-cage hook source files:
  (a) contain NO inline ANSI escape sequences (\\x1b / \\033) in code,
  (b) contain NO literal `[rabbit]` brand prefix in code,
  (c) contain NO literal `━━━` bar in code,
  (d) contain NO direct `rabbit_print(` CALL (the named wrappers are the
      public API; string-id calls at hook call sites are forbidden by
      Inv 87),
  (e) contain NO manual `"\\n".join(` aggregation pattern (only
      `rabbit_block` adds the leading newline; Inv 87, 90),
  (f) import `rabbit_block` from the shared renderer module.
"""
import os
import re
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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


def _strip_docstring_and_comments(source: str) -> str:
    """Drop the module docstring and any pure-comment lines so we search
    only executable / import code regions."""
    src = source
    m = re.search(r'^\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*\n', src, re.MULTILINE)
    if m and m.start() < 500:
        src = src[:m.start()] + src[m.end():]
    kept = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        kept.append(line)
    return "\n".join(kept)


def count_occurrences(source: str, needle: str) -> int:
    return _strip_docstring_and_comments(source).count(needle)


def count_pattern(source: str, pattern: str) -> int:
    return len(re.findall(pattern, _strip_docstring_and_comments(source)))


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

    body = _strip_docstring_and_comments(src)

    # (a) No direct ANSI escape sequences in code: \x1b or \033 literal
    n_x1b = body.count("\\x1b")
    n_033 = body.count("\\033")
    if n_x1b == 0 and n_033 == 0:
        ok(f"{name} contains no inline \\x1b or \\033 ANSI escapes in code")
    else:
        fail_t(f"{name} contains inline ANSI escapes (\\x1b={n_x1b}, \\033={n_033})")

    # (b) No literal `[rabbit]` brand
    n_rab = body.count("[rabbit]")
    if n_rab == 0:
        ok(f"{name} contains no literal [rabbit] brand in code")
    else:
        fail_t(f"{name} contains {n_rab} literal [rabbit] brand strings in code")

    # (c) No literal `━━━` bar
    n_bar = body.count("━━━")
    if n_bar == 0:
        ok(f"{name} contains no literal ━━━ bar in code")
    else:
        fail_t(f"{name} contains {n_bar} literal ━━━ bars in code")

    # (d) No direct `rabbit_print(` CALL. The import line "from rabbit_print
    # import ..." is allowed; only call sites are forbidden. The pattern
    # `rabbit_print(` does NOT match the import statement (the import has
    # no trailing `(` immediately after the module name).
    n_call = len(re.findall(r"\brabbit_print\(", body))
    if n_call == 0:
        ok(f"{name} contains no direct `rabbit_print(` call (Inv 87)")
    else:
        fail_t(f"{name} contains {n_call} direct `rabbit_print(` call(s); use named wrappers instead")

    # (e) No manual `"\n" + "\n".join(` aggregation in code. rabbit_block is
    # the sole owner of the leading newline (Inv 87, 90). The forbidden
    # pattern is the leading-newline-then-join shape; plain `"\n".join(`
    # inside a renderer (composing a multi-line banner + sub-lines block
    # WITHOUT a leading newline) is allowed — only the outer aggregation
    # via rabbit_block adds the leading '\n'.
    n_join = len(re.findall(
        r"""["']\\n["']\s*\+\s*["']\\n["']\.join\(""", body,
    ))
    if n_join == 0:
        ok(f"{name} contains no manual `\"\\n\" + \"\\n\".join(` aggregation (Inv 87)")
    else:
        fail_t(f"{name} contains {n_join} manual `\"\\n\" + \"\\n\".join(` aggregation(s); use rabbit_block instead")

    # (f) Imports rabbit_block from rabbit_print
    if re.search(r"from rabbit_print import[\s\S]*?\brabbit_block\b", src):
        ok(f"{name} imports `rabbit_block` from rabbit_print")
    else:
        fail_t(f"{name} does NOT import `rabbit_block` from rabbit_print (Inv 87)")
    print()

print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
