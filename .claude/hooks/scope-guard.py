#!/usr/bin/env python3
"""scope-guard.py v2.0.0 — PreToolUse hook enforcing repo-wide default-deny.

Any write inside the repo root is denied unless:
  (a) the target basename is on the filename allowlist, or
  (b) a .rabbit-scope-active marker exists in some ancestor of the target, or
  (c) a .rabbit-scope-active-<feature> per-feature marker exists at repo root
      and the target is inside that feature's directory, or
  (d) a .rabbit-scope-override file at repo root grants a session/one-time bypass.

Writes outside the repo root are unrestricted.
The .rabbit-scope-active marker file itself is always exempt.
"""

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


def _git_toplevel(start: Path) -> Optional[Path]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        return None


REPO_ROOT = _git_toplevel(Path(__file__).resolve().parent)


def abspath(p: str) -> str:
    if p.startswith("/"):
        return p
    return os.path.join(os.getcwd(), p)


def walk_up_find(target: str, want: str) -> Optional[str]:
    """Walk up from target's parent looking for a directory containing 'want'."""
    d = os.path.dirname(target)
    while d not in ("", "/", "."):
        if os.path.exists(os.path.join(d, want)):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def find_feature_path(repo_root: Path, feature: str) -> Optional[str]:
    """Run find-feature.py; return repo-relative path or None."""
    script = repo_root / ".claude" / "features" / "contract" / "scripts" / "find-feature.py"
    if not script.exists():
        return None
    try:
        import sys
        out = subprocess.check_output(
            [sys.executable, str(script), str(repo_root), "lookup", feature],
            stderr=subprocess.DEVNULL,
        )
        s = out.decode().strip()
        return s or None
    except Exception:
        return None


def decide(target: str) -> Tuple[bool, str]:
    """Decide on one target. Returns (allow, reason_message).
    On deny, reason_message is the full DENY message; on allow, it's the ALLOW reason."""
    abs_path = abspath(target)
    # Resolve symlinks so a symlink into a protected area is caught.
    if os.path.islink(abs_path):
        try:
            abs_path = os.path.realpath(abs_path)
        except Exception:
            pass
    base = os.path.basename(abs_path)

    # 1. Outside the repo entirely -> always allow
    if REPO_ROOT is None or not abs_path.startswith(str(REPO_ROOT) + "/"):
        return True, "ALLOW (outside repo root)"

    # 2. Marker file itself is always exempt
    if base == ".rabbit-scope-active" or base.startswith(".rabbit-scope-active-"):
        return True, "ALLOW (scope marker is exempt)"

    # 3. Allowlisted filenames -> always allow
    if base in ("settings.json", "settings.local.json", ".gitignore", ".rabbit-scope-override"):
        return True, "ALLOW (allowlisted filename)"

    # 3b. Path-prefix allowlist — always allow (dispatcher metadata + bug/backlog storage).
    # .rabbit/ is required so rabbit-feature-touch can write
    # .rabbit/impl-suggestion-<feature>.json and .rabbit/tdd-report-<feature>.json
    # during normal feature work without needing a session override.
    if (
        abs_path.startswith(str(REPO_ROOT) + "/.claude/bugs/")
        or abs_path.startswith(str(REPO_ROOT) + "/.claude/backlogs/")
        or abs_path.startswith(str(REPO_ROOT) + "/.rabbit/")
    ):
        return True, "ALLOW (path-prefix allowlist: bug/backlog/dispatcher metadata)"

    # 4a. Per-feature scope markers
    for per_marker in glob.glob(str(REPO_ROOT) + "/.rabbit-scope-active-*"):
        if not os.path.isfile(per_marker):
            continue
        per_feature = os.path.basename(per_marker)[len(".rabbit-scope-active-"):]
        if not per_feature or per_feature == "*":
            continue
        per_path = find_feature_path(REPO_ROOT, per_feature)
        if not per_path:
            continue
        per_abs = str(REPO_ROOT) + "/" + per_path
        if abs_path.startswith(per_abs):
            return True, f"ALLOW (per-feature scope marker: {per_feature})"

    # 4. Active scope marker anywhere in ancestor chain
    if walk_up_find(abs_path, ".rabbit-scope-active"):
        scope_marker = REPO_ROOT / ".rabbit-scope-active"
        scope_feature = ""
        try:
            scope_feature = scope_marker.read_text().strip()
        except Exception:
            pass
        feature_path = find_feature_path(REPO_ROOT, scope_feature) if scope_feature else None
        if feature_path:
            feature_abs = str(REPO_ROOT) + "/" + feature_path
            if not abs_path.startswith(feature_abs):
                return False, (
                    f"DENY write to '{abs_path}' denied: outside active scope "
                    f"'{scope_feature}' (allowed: {feature_abs}/). "
                    "Use dispatch-feature-edit.py for cross-feature work."
                )
            # 4c. Within scoped feature — deny if feature is in test-green state
            feature_json = Path(feature_abs) / "feature.json"
            tdd_state = ""
            try:
                tdd_state = json.loads(feature_json.read_text()).get("tdd_state", "")
            except Exception:
                pass
            if tdd_state == "test-green":
                # Override marker — human-approved bypass of test-green deny
                allow_msg = _consume_override()
                if allow_msg:
                    return True, allow_msg
                return False, (
                    f"DENY write to '{abs_path}' denied: feature '{scope_feature}' "
                    "is in test-green state. Invoke the rabbit-feature-touch skill "
                    "to reset the TDD state before editing."
                )
        return True, "ALLOW (under active scope)"

    # 4b-override. Override marker — human-approved bypass for no-scope-marker case
    allow_msg = _consume_override()
    if allow_msg:
        return True, allow_msg

    # 5. Default deny — Inv 52: present three explicit options.
    # Force a decision point rather than framing override as a silent
    # procedural next step (the rationalization pattern BUG-1 captured).
    return False, (
        f"DENY write to '{abs_path}' denied: no active scope marker and "
        "file is not on the allowlist (settings.json, settings.local.json, "
        ".gitignore, .rabbit-scope-override).\n"
        "\n"
        "Choose one of the three options below. Both override options "
        "require explicit in-conversation user confirmation and MUST NOT "
        "be written speculatively.\n"
        "\n"
        "  (1) SESSION OVERRIDE — bypasses scope-guard for the entire "
        "session. Requires explicit in-conversation user confirmation "
        "before writing '.rabbit-scope-override' with content 'session'.\n"
        "\n"
        "  (2) ONE-TIME OVERRIDE — bypasses scope-guard for a single "
        "write only. Requires explicit in-conversation user confirmation "
        "before writing '.rabbit-scope-override' with content 'one-time'.\n"
        "\n"
        "  (3) USE rabbit-feature-touch (recommended) — the correct "
        "governed path for feature edits. Invokes the TDD cycle, advances "
        "tdd_state, and creates a PR; no override needed."
    )


def _consume_override() -> Optional[str]:
    """If override file present, consume per its mode and return ALLOW message."""
    override_file = REPO_ROOT / ".rabbit-scope-override"
    used_file = REPO_ROOT / ".rabbit-scope-override-used"
    if not override_file.is_file():
        return None
    try:
        mode = override_file.read_text()
    except Exception:
        return None
    mode = "".join(c for c in mode if not c.isspace())
    if mode == "session":
        return "ALLOW (session override active)"
    if mode == "one-time":
        try:
            override_file.unlink()
        except Exception:
            pass
        try:
            used_file.touch()
        except Exception:
            pass
        return "ALLOW (one-time override consumed)"
    return None


# ---------- Bash command target extraction ----------

_HEREDOC_RE = re.compile(
    r"<<[- ]*['\"]?([A-Za-z_]\w*)['\"]?[^\n]*\n(.*\n)*?\1\n?",
    re.DOTALL,
)


def _strip_quotes(seg: str) -> str:
    # Remove single-quoted regions
    s = re.sub(r"'[^']*'", " ", seg)
    # Remove double-quoted regions (DOTALL so multi-line strings are fully stripped)
    s = re.sub(r'"[^"]*"', " ", s, flags=re.DOTALL)
    return s


def extract_bash_targets(cmd: str) -> List[str]:
    """Extract write targets from a bash command string (conservative)."""
    # Join backslash-newline continuations so quoted args are on one line
    cmd = cmd.replace("\\\n", " ")
    # Strip heredoc bodies
    cmd = _HEREDOC_RE.sub(" ", cmd)
    # Split on ; | &
    segments = re.split(r"[;|&]", cmd)
    targets: List[str] = []

    for seg in segments:
        seg = seg.lstrip()
        if not seg:
            continue
        stripped = _strip_quotes(seg)

        # > path or >> path
        for m in re.finditer(r">>?\s*([^\s<>|&;]+)", stripped):
            targets.append(m.group(1))

        # tee [flags] path
        for m in re.finditer(r"\btee\s+(?:-[a-z]+\s+)?([^\s<>|&;]+)", stripped):
            targets.append(m.group(1))

        # sed -i ... last-arg
        for m in re.finditer(r"\bsed\s+-i\s+([^\s<>|&;]+(?:\s+[^\s<>|&;]+)*)", stripped):
            parts = m.group(1).split()
            if parts:
                targets.append(parts[-1])

        # cp / mv last arg
        for verb in ("cp", "mv"):
            pattern = (
                r"\b" + verb + r"\s+(?:-[a-zA-Z]+\s+)*"
                r"[^\s<>|&;]+(?:\s+[^\s<>|&;]+)+"
            )
            for m in re.finditer(pattern, stripped):
                parts = [
                    p for p in m.group(0).split()
                    if p not in (verb,)
                    and not p.startswith("-")
                    and not re.match(r"^\d+$", p)
                    and not re.match(r"^\d*>>?", p)
                ]
                if parts:
                    targets.append(parts[-1])

        # Helper: pretokenize for verb-args extraction; drop flag and
        # redirect tokens (e.g., '2>/dev/null', '>foo', '>>bar') so they
        # are not mistaken for write targets of the verb.
        def _verb_args(rest: str) -> list:
            out = []
            for tok in rest.split():
                if not tok or tok.startswith("-"):
                    continue
                if re.match(r"^\d*>>?", tok) or tok.startswith("<"):
                    continue
                out.append(tok)
            return out

        # rm path[s]
        m = re.match(r"\s*rm\s+(.*)", stripped)
        if m:
            targets.extend(_verb_args(m.group(1)))

        # touch path[s]
        m = re.match(r"\s*touch\s+(.*)", stripped)
        if m:
            targets.extend(_verb_args(m.group(1)))

        # mkdir path[s]
        m = re.match(r"\s*mkdir\s+(.*)", stripped)
        if m:
            targets.extend(_verb_args(m.group(1)))

    return targets


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    targets: List[str] = []
    if tool in ("Write", "Edit"):
        t = tool_input.get("file_path", "")
        if t:
            targets.append(t)
    elif tool == "Bash":
        cmd = tool_input.get("command", "")
        if cmd:
            targets.extend(extract_bash_targets(cmd))

    for t in targets:
        if not t:
            continue
        allow, msg = decide(t)
        if not allow:
            sys.stderr.write(f"scope-guard: {msg}\n")
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
