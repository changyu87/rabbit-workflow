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

import json
import os


def print_result(text: str, icon: str, color: str) -> dict:
    """Tagged dict for an alert line that the dispatcher renders via
    rabbit_subline and joins into the Stop hook systemMessage."""
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


def banner_result(message_id: str) -> dict:
    """Tagged dict for a banner line; dispatcher renders via rabbit_print(message_id)
    using the banner format (decorated with ━━━ bars)."""
    return {"type": "banner", "message_id": message_id}


def subline_result(text: str, color: str = "green") -> dict:
    """Tagged dict for a sub-line; dispatcher renders via rabbit_subline(text, color)
    without icon decoration."""
    return {"type": "subline", "text": text, "color": color}


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


def welcome_with_policy(policy_source: str, sublines=None, *, repo_root: str):
    """Return [welcome banner_result, *subline_results, policy inject_result].

    policy_source is repo-root-relative; may be a single file or a
    directory whose *.md files are concatenated alphabetically (same
    semantics as check_counter_threshold_refresh source).

    sublines is an optional list of {text: str, color: str (default 'green')}.
    When provided, one subline_result per entry is inserted between the
    banner and the inject. When absent or empty, only [banner, inject].

    On unreadable source returns a single error_result (NOT a list).
    """
    full = os.path.join(repo_root, policy_source)
    try:
        content = _read_source(full)
    except (FileNotFoundError, OSError) as e:
        return error_result(f"welcome policy source unreadable: {e}")
    results = [banner_result("welcome")]
    for sl in (sublines or []):
        results.append(subline_result(sl["text"], sl.get("color", "green")))
    results.append(inject_result(content))
    return results


def check_drift_regenerate(target: str, producer: str, alert: dict,
                            *, feature_dir: str, repo_root: str):
    """Run the named content producer and compare to target on disk.

    On match: return ok_result(). On drift (or missing target): write
    producer output to target and return [print_result, inject_result].
    On producer exception or import failure: return error_result(...).

    Lazy-imports lib.producers so this module loads even before the
    producers sibling lands.
    """
    try:
        from lib import producers  # noqa: PLC0415
    except ImportError as e:
        return error_result(f"lib.producers unavailable: {e}")
    try:
        content = producers.call_producer(producer, {},
                                          feature_dir=feature_dir,
                                          repo_root=repo_root)
    except Exception as e:  # noqa: BLE001 - dispatcher catches any producer fault
        return error_result(f"producer {producer!r} failed: {e}")

    full_target = os.path.join(repo_root, target)
    current = ""
    if os.path.isfile(full_target):
        try:
            with open(full_target) as f:
                current = f.read()
        except OSError as e:
            return error_result(f"target unreadable: {e}")
    if content == current:
        return ok_result()

    parent = os.path.dirname(full_target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(full_target, "w") as f:
        f.write(content)
    return [
        print_result(alert["text"], alert["icon"], alert["color"]),
        inject_result(content),
    ]


def _enumerate_features(repo_root: str):
    """Yield (feature_name, feature_dir, feature_json_dict) for every
    feature directory under .claude/features/. Skips malformed
    feature.json files silently. Order: alphabetical by feature name.
    Shared helper for check_manifest_drift and iterate_configurables_*.
    """
    features_root = os.path.join(repo_root, ".claude", "features")
    if not os.path.isdir(features_root):
        return
    for name in sorted(os.listdir(features_root)):
        fdir = os.path.join(features_root, name)
        fj = os.path.join(fdir, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        yield name, fdir, data


def check_manifest_drift(alert: dict, *, repo_root: str) -> dict:
    """Re-run every feature's MANIFEST via the publish APIs. Return a
    print_result naming features whose publish calls produced a non-no-op
    write (substring "no-op" absent from CheckResult.messages). On all-noop
    return ok_result. {names} in alert.text is substituted by the
    comma-joined feature names in alphabetical order.

    Lazy-imports lib.publish so this module can be loaded standalone.
    """
    try:
        from lib import publish  # noqa: PLC0415
    except ImportError as e:
        return error_result(f"lib.publish unavailable: {e}")

    drifted = []
    for name, fdir, data in _enumerate_features(repo_root):
        manifest = data.get("manifest")
        if not isinstance(manifest, list) or not manifest:
            continue
        for entry in manifest:
            api_name = entry.get("api")
            args = entry.get("args", {}) or {}
            fn = getattr(publish, api_name, None)
            if fn is None:
                drifted.append(name)
                break
            try:
                result = fn(**args, feature_dir=fdir, repo_root=repo_root)
            except Exception:  # noqa: BLE001
                drifted.append(name)
                break
            messages = getattr(result, "messages", []) or []
            if not any("no-op" in m for m in messages):
                drifted.append(name)
                break

    if not drifted:
        return ok_result()
    names = ", ".join(sorted(set(drifted)))
    return print_result(alert["text"].replace("{names}", names),
                        alert["icon"], alert["color"])


def _resolve_marker_value(repo_root: str, storage: dict) -> str:
    """marker-file semantics: present -> 'false', absent -> 'true'.
    Matches the rabbit-cage human-approval CONFIGURATION example
    (values.true => delete_marker, values.false => write_marker).
    """
    path = storage.get("path")
    if not path:
        return ""
    return "false" if os.path.isfile(os.path.join(repo_root, path)) else "true"


def _resolve_json_key_value(repo_root: str, storage: dict, default: str) -> str:
    """Read storage.key (dotted path) from storage.file. Returns stringified
    value, or `default` if file is missing, unreadable, or key absent.
    Booleans stringify to 'true' / 'false'.
    """
    file_rel = storage.get("file")
    key_path = storage.get("key")
    if not file_rel or not key_path:
        return default
    full = os.path.join(repo_root, file_rel)
    if not os.path.isfile(full):
        return default
    try:
        with open(full) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    cursor = data
    for part in key_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    if isinstance(cursor, bool):
        return "true" if cursor else "false"
    return str(cursor)


def _reverse_map_json_value(raw: str, configurable: dict) -> str:
    """Translate a raw json-key stored value to its user-facing label by
    reverse-lookup through the configurable's values map.
    Checks whether `raw` is already a user-facing key; otherwise finds the
    values entry whose set_json_key args.value matches raw.
    Returns raw unchanged if no translation is found.
    """
    values = configurable.get("values") or {}
    if raw in values:
        return raw
    for user_key, mutation in values.items():
        if mutation.get("api") == "set_json_key":
            if str(mutation.get("args", {}).get("value", "")) == raw:
                return user_key
    return raw


def _resolve_current_value(repo_root: str, configurable: dict):
    """Return the current string value of a configurable for alert-on
    comparison, or None if storage type is action-style (json-array*).
    For json-key storage the raw stored value is translated to its user-facing
    label via reverse lookup through the configurable's values map.
    """
    storage = configurable.get("storage") or {}
    stype = storage.get("type")
    default = configurable.get("default", "")
    if stype == "marker-file":
        return _resolve_marker_value(repo_root, storage)
    if stype == "json-key":
        raw = _resolve_json_key_value(repo_root, storage, default)
        return _reverse_map_json_value(raw, configurable)
    # json-array / json-array-templated are action-style; no scalar value
    return None


def iterate_configurables_alerts(*, repo_root: str):
    """Walk every feature's CONFIGURATION array; for each configurable whose
    current value matches alert-on, return its alert-message as a
    print_result. Order: alphabetical by feature name x declaration order.
    Returns a list (possibly empty).
    """
    out = []
    for name, fdir, data in _enumerate_features(repo_root):
        configuration = data.get("configuration")
        if not isinstance(configuration, list):
            continue
        for cfg in configuration:
            alert_on = cfg.get("alert-on")
            alert_msg = cfg.get("alert-message")
            if alert_on is None or not isinstance(alert_msg, dict):
                continue
            current = _resolve_current_value(repo_root, cfg)
            if current is None:
                continue
            if current == alert_on:
                out.append(print_result(alert_msg["text"],
                                        alert_msg["icon"],
                                        alert_msg["color"]))
    return out


def iterate_configurables_banner(*, repo_root: str):
    """Like iterate_configurables_alerts but for SessionStart. Each active
    override emits a multi-line print_result whose text is

        <alert.text>
          revoke with: /rabbit-config <subcommand> <default>

    If the configurable has no `default`, the revoke target falls back to
    the literal string '<unknown>'. Icon and color come from
    alert-message. Returns a list (possibly empty).
    """
    out = []
    for name, fdir, data in _enumerate_features(repo_root):
        configuration = data.get("configuration")
        if not isinstance(configuration, list):
            continue
        for cfg in configuration:
            alert_on = cfg.get("alert-on")
            alert_msg = cfg.get("alert-message")
            if alert_on is None or not isinstance(alert_msg, dict):
                continue
            current = _resolve_current_value(repo_root, cfg)
            if current is None or current != alert_on:
                continue
            subcommand = cfg.get("subcommand", cfg.get("id", "?"))
            revoke_value = cfg.get("default", "<unknown>")
            text = (f"{alert_msg['text']}\n"
                    f"  revoke with: /rabbit-config {subcommand} {revoke_value}")
            out.append(print_result(text, alert_msg["icon"], alert_msg["color"]))
    return out
