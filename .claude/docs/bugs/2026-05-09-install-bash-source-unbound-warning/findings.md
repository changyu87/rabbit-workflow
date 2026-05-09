# findings — install.sh BASH_SOURCE[0] unbound warning under curl-pipe mode

> Companion to [`bug.json`](./bug.json). Detailed analysis + proposed fix.

## Symptom (verbatim)

User ran the documented curl-pipe install on tcsh:

```tcsh
[cyxu @ atltigr0358 ai_usage] $ curl -fsSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
bash: line 49: BASH_SOURCE[0]: unbound variable
rabbit-workflow installed to /proj/dxio_delivery3/cyxu/citip/cit_4/ws1/ai_usage (minimal: .claude/ + CLAUDE.md only)
```

Install completed successfully (`.claude/` and `CLAUDE.md` were copied,
default minimal-mode behavior was correct), but a confusing warning was
emitted to stderr just before the success message.

## Root cause

`install.sh` opens with:

```bash
set -euo pipefail
```

The `-u` part (`set -u` aka `nounset`) makes referencing **any unset
variable** a hard error.

Line 49 is:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
```

`BASH_SOURCE` is a bash array that contains the source-file path of the
currently executing script. Its values when the script runs:

- **From a real file** (`./install.sh ...` or `bash install.sh ...`):
  `${BASH_SOURCE[0]}` = the absolute path to install.sh. SCRIPT_DIR
  resolves correctly. Local install path works.
- **From process substitution** (`bash <(curl ...)` in bash):
  `${BASH_SOURCE[0]}` = a path like `/dev/fd/63`. SCRIPT_DIR resolves
  to that fd path; the subsequent `[ -d "$SCRIPT_DIR/.claude" ]` check
  fails (no .claude/ in /dev/fd/), so the script falls into the
  curl-tarball branch correctly. **No warning.**
- **From stdin** (`curl ... | bash`): the script is read from bash's
  stdin without a file backing. **`BASH_SOURCE` is empty** —
  `${BASH_SOURCE[0]}` references an unbound array element. `set -u`
  triggers the warning. The expansion fails noisily, but because:
  - `2>/dev/null` would have caught the cd-stderr, NOT the
    expansion-time error (which is emitted by bash's parser/expander
    BEFORE the redirect takes effect)
  - The chain ends with `|| echo ""`, so the assignment overall succeeds
    with `SCRIPT_DIR=""`
  - The empty SCRIPT_DIR makes `[[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.claude" ]]`
    fail, so the script falls into the curl-tarball branch correctly

So functionality is unaffected. Only the cosmetic warning leaks.

## Why this matters

The README documents `curl ... | bash` as the canonical curl install for
both tcsh and other non-bash shells (since `bash <(...)` doesn't parse
in csh-family shells). Every user who follows that recommended path will
see the warning. They will reasonably wonder:

- Did the install actually succeed?
- Is something missing?
- Is this a security warning?

None of those concerns is justified, but the warning prompts them.

## One-line fix

Replace `${BASH_SOURCE[0]}` with `${BASH_SOURCE[0]:-}` on line 49 of
`install.sh`. The `:-` provides an empty-string default when the variable
is unset, satisfying `set -u` without changing any downstream behavior:

```diff
-SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
+SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-}")" 2>/dev/null && pwd || echo "")"
```

After the fix:

| Invocation mode | `BASH_SOURCE[0]` before | `${BASH_SOURCE[0]:-}` after |
|---|---|---|
| `bash install.sh ...` (file) | path to script | path to script (no change) |
| `bash <(curl ...) ...` (process subst) | `/dev/fd/63` | `/dev/fd/63` (no change) |
| `curl ... \| bash` (stdin) | unbound → warning | empty string → silent |

In the third case, `dirname ""` returns `.`, `cd .` succeeds, and SCRIPT_DIR
becomes the user's CWD. The subsequent `[ -d "$SCRIPT_DIR/.claude" ]`
check might now pass IF the user happens to have a `.claude/` in CWD —
which would route the script to local-copy mode and probably break (the
local `.claude/` isn't necessarily this rabbit-workflow installation).

**Edge-case mitigation needed:** to be safe, also guard the local-mode
detection more tightly. Two reasonable approaches:

### Option A (minimal — fix only the warning)

The diff above. Accept the small theoretical risk that an unrelated
`.claude/` in CWD could be mistaken for a rabbit checkout.

### Option B (defensive — fix the warning AND tighten the local-mode detection)

```diff
-SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
-
-if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.claude" ]]; then
+RAW_SOURCE="${BASH_SOURCE[0]:-}"
+if [[ -n "$RAW_SOURCE" && -f "$RAW_SOURCE" ]]; then
+    SCRIPT_DIR="$(cd "$(dirname "$RAW_SOURCE")" && pwd)"
+else
+    SCRIPT_DIR=""
+fi
+
+if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.claude" && -f "$SCRIPT_DIR/install.sh" ]]; then
     SRC="$SCRIPT_DIR"
 else
     ...
```

Adds two checks:
- `[ -f "$RAW_SOURCE" ]` — only treat as local mode if BASH_SOURCE points
  at a real file (not stdin, not /dev/fd/N)
- `[ -f "$SCRIPT_DIR/install.sh" ]` — only treat as local mode if the
  script alongside install.sh is itself this install.sh (cheap sanity
  check)

Recommend **Option A** for now (smaller diff, addresses the reported
issue, the edge case in B is theoretical and a separate concern).

## Test plan after fix

The existing `test/test-install.sh` invokes install.sh as a real file
via `"$INSTALL" ...` — that exercises mode 1 only. Recommend adding a
case t16 that pipes install.sh through bash:

```bash
t16_curl_pipe_mode_no_warning() {
    out="$(cat "$INSTALL" | bash -s -- "$DIR" 2>&1)"
    # success required AND no 'unbound variable' anywhere in stderr/stdout
    [[ -d "$DIR/.claude" && -f "$DIR/CLAUDE.md" ]] && \
        ! echo "$out" | grep -qi 'unbound variable'
}
run "16: curl-pipe mode: no unbound-variable warning" t16_curl_pipe_mode_no_warning
```

This regression-protects the fix.

## Related

- `auto-refresh` feature: also uses `BASH_SOURCE[0]` (in `rbt-refresh.sh`)
  but that script is invoked by Claude Code's hook system from a real
  file path — not vulnerable to the same issue. No fix needed there.
- The `--all` flag, the `USER`-placeholder fix, and the install discipline
  documented in `install-distribute/spec.md` are all unaffected by this
  bug. The warning is purely a noise leak; functionality is correct.

## Lifecycle

- **Filed:** 2026-05-09 (this bug)
- **Status:** open
- **Severity:** medium (cosmetic but every new curl-pipe user sees it)
- **Related feature:** install-distribute
- **Proposed close criterion:** the one-line fix lands on main + a t16
  regression test is added to `test/test-install.sh` + manual verification
  via `curl ... | bash` shows no warning.
