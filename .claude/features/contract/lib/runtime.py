"""contract.lib.runtime — API library for the runtime APIs invoked by the
per-event dispatcher hooks (Stop, SessionStart, UserPromptSubmit). Each
function implements one runtime API call declared in a feature's RUNTIME
section and returns one or more typed result dicts.

Return-type vocabulary (built via the four factory helpers below):
    print   {"type": "print",  "text": str, "icon": str, "color": str}
    inject  {"type": "inject", "content": str}
    ok      {"type": "ok"}
    error   {"type": "error", "message": str}

Functions that may emit both a print and an inject return a list of two
results in [print, inject] order. The single-result APIs return one dict.
The iterate_configurables_* APIs always return a (possibly empty) list of
print results.

Path-arg convention: every path arg accepted by these APIs is repo-root-
relative unless explicitly noted. (This differs from lib.producers, which
resolves relative paths against feature_dir.)

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native per-event
    dispatchers that subsume this library.
"""

import os


def print_result(text: str, icon: str, color: str) -> dict:
    """Tagged dict for an alert line that the dispatcher renders via
    rabbit_print and joins into the Stop hook systemMessage."""
    return {"type": "print", "text": text, "icon": icon, "color": color}


def inject_result(content: str) -> dict:
    """Tagged dict for additional context the dispatcher attaches to the
    Stop/SessionStart/UserPromptSubmit additionalContext field."""
    return {"type": "inject", "content": content}


def ok_result() -> dict:
    """Tagged dict for the no-op case — dispatcher drops these."""
    return {"type": "ok"}


def error_result(message: str) -> dict:
    """Tagged dict for an internal failure — dispatcher logs to stderr and
    does NOT surface to Claude."""
    return {"type": "error", "message": message}


def check_marker_alert(path: str, content, alert: dict, *, repo_root: str) -> dict:
    """If the marker at `path` (repo-root-relative) exists, return a print
    result built from `alert` ({text, icon, color}). If `content` is not
    None, the marker file must also contain exactly that string; otherwise
    treat as absent.
    """
    full = os.path.join(repo_root, path)
    if not os.path.isfile(full):
        return ok_result()
    if content is not None:
        try:
            with open(full) as f:
                if f.read() != content:
                    return ok_result()
        except OSError:
            return ok_result()
    return print_result(alert["text"], alert["icon"], alert["color"])


def check_marker_consume_alert(path: str, alert: dict, *, repo_root: str) -> dict:
    """If the marker at `path` (repo-root-relative) exists, delete it and
    return a print result built from `alert`. If `alert.text` contains the
    literal substring `{marker-content}`, the (stripped) marker contents
    are substituted in before deletion. Missing marker returns ok_result.
    Does not mutate the caller's `alert` dict.
    """
    full = os.path.join(repo_root, path)
    if not os.path.isfile(full):
        return ok_result()
    text = alert["text"]
    if "{marker-content}" in text:
        try:
            with open(full) as f:
                marker_content = f.read().strip()
        except OSError:
            marker_content = ""
        text = text.replace("{marker-content}", marker_content)
    try:
        os.remove(full)
    except OSError:
        pass
    return print_result(text, alert["icon"], alert["color"])


DEFAULT_REFRESH_THRESHOLD = 20


def _read_threshold(env_var: str) -> int:
    raw = os.environ.get(env_var)
    if raw is None:
        return DEFAULT_REFRESH_THRESHOLD
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_REFRESH_THRESHOLD


def _read_source(full_source: str) -> str:
    """Read source content. If full_source is a directory, concat every
    *.md file inside it in alphabetical filename order. Raises
    FileNotFoundError or OSError if the path does not exist.
    """
    if os.path.isdir(full_source):
        parts = []
        for name in sorted(os.listdir(full_source)):
            if name.endswith(".md"):
                with open(os.path.join(full_source, name)) as f:
                    parts.append(f.read())
        return "".join(parts)
    with open(full_source) as f:
        return f.read()


def check_counter_threshold_refresh(counter: str, env_var: str, source: str,
                                    *, repo_root: str) -> dict:
    """Increment counter file each invocation; on threshold, reset counter
    to 0 and return inject_result whose content is read from `source`
    (repo-root-relative file, OR a directory whose *.md files are
    concatenated alphabetically). Below threshold returns ok_result.
    Missing or unreadable source returns error_result.
    """
    counter_full = os.path.join(repo_root, counter)
    threshold = _read_threshold(env_var)

    current = 0
    if os.path.isfile(counter_full):
        try:
            current = int(open(counter_full).read().strip())
        except (OSError, ValueError):
            current = 0
    new_val = current + 1

    if new_val < threshold:
        parent = os.path.dirname(counter_full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(counter_full, "w") as f:
            f.write(str(new_val))
        return ok_result()

    # at or above threshold: reset and inject
    source_full = os.path.join(repo_root, source)
    try:
        content = _read_source(source_full)
    except (FileNotFoundError, OSError) as e:
        return error_result(f"counter refresh source unreadable: {e}")
    with open(counter_full, "w") as f:
        f.write("0")
    return inject_result(content)
