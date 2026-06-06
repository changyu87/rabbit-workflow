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

Path-arg convention: every path arg accepted by these APIs is repo-root-
relative unless explicitly noted. (This differs from lib.producers, which
resolves relative paths against feature_dir.)

Version: 1.16.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native per-event
    dispatchers that subsume this library.
"""

import datetime
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time


def _auto_evolve_active(repo_root: str) -> bool:
    """True iff the .rabbit-auto-evolve-active marker is present at repo root.
    Sole reader of the marker; matches the _resolve_marker_value pattern.
    """
    return os.path.isfile(os.path.join(repo_root, ".rabbit-auto-evolve-active"))


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


def banner_result(text: str, icon: str, color: str) -> dict:
    """Tagged dict for a banner line; dispatcher renders via
    rabbit_print(text, icon, color, format='banner') (decorated with ━━━ bars).
    Text/icon/color are caller-supplied — no registry indirection."""
    return {"type": "banner", "text": text, "icon": icon, "color": color}


def subline_result(text: str, color: str = "green") -> dict:
    """Tagged dict for a sub-line; dispatcher renders via rabbit_subline(text, color)
    without icon decoration."""
    return {"type": "subline", "text": text, "color": color}


def check_marker_alert(path: str, content, alert: dict, *, repo_root: str) -> dict:
    """If the marker at `path` (repo-root-relative) exists, return a print
    result built from `alert` ({text, icon, color}). If `content` is not
    None, the marker file must also contain exactly that string; otherwise
    treat as absent.

    Inv 54 — suppressed under auto-evolve: when .rabbit-auto-evolve-active is
    present, this live per-feature alert is a no-op (ok_result). During
    autonomous mode the auto-evolve composite banner (emit_auto_evolve_banner /
    emit_auto_evolve_stop_line, Inv 55) is the single replacement surface, so
    the per-feature override alert must not double up on it.
    """
    if _auto_evolve_active(repo_root):
        return ok_result()
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

    # at or above threshold: reset and emit [print banner, inject]
    source_full = os.path.join(repo_root, source)
    try:
        content = _read_source(source_full)
    except (FileNotFoundError, OSError) as e:
        return error_result(f"counter refresh source unreadable: {e}")
    with open(counter_full, "w") as f:
        f.write("0")
    return [
        print_result(f"policy refreshed (every {threshold} prompts)", "🔄", "green"),
        inject_result(content),
    ]


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
    results = [banner_result(
        "Welcome — governing policies loaded", "✅", "green",
    )]
    for sl in (sublines or []):
        results.append(subline_result(sl["text"], sl.get("color", "green")))
    results.append(inject_result(content))
    return results


def check_drift_regenerate(target: str, producer: str, alert: dict,
                            args=None,
                            *, feature_dir: str, repo_root: str):
    """Run the named content producer and compare to target on disk.

    args - optional dict of producer-specific kwargs forwarded to
    lib.producers.call_producer. Defaults to None (treated as {}). Per
    spec Inv 39, this parameter exists because producers like
    generate-claude-md require named kwargs (policy_source,
    header_source) declared in the RUNTIME entry's args block; a
    hardcoded-empty-args call path leaves the producer unable to
    execute. The dispatcher passes args through from the feature's
    RUNTIME declaration.

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
        content = producers.call_producer(producer, args or {},
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
    Shared helper for check_manifest_drift.
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
        # Walk EVERY entry; do NOT break early. A manifest may chain
        # publishers — e.g. publish_settings followed by N publish_hook
        # calls that read-modify-write the same settings.json. Breaking
        # after the first non-no-op leaves the file half-built until the
        # next full publish loop runs, observable as missing hooks after
        # any Stop-event surface-drift rebuild.
        for entry in manifest:
            api_name = entry.get("api")
            args = entry.get("args", {}) or {}
            fn = getattr(publish, api_name, None)
            if fn is None:
                if name not in drifted:
                    drifted.append(name)
                continue
            try:
                result = fn(**args, feature_dir=fdir, repo_root=repo_root)
            except Exception:  # noqa: BLE001
                if name not in drifted:
                    drifted.append(name)
                continue
            messages = getattr(result, "messages", []) or []
            if not any("no-op" in m for m in messages):
                if name not in drifted:
                    drifted.append(name)

    if not drifted:
        return ok_result()
    names = ", ".join(sorted(set(drifted)))
    return print_result(alert["text"].replace("{names}", names),
                        alert["icon"], alert["color"])


def _marker_polarity(configurable: dict):
    """Derive (present_value, absent_value) from the configurable's OWN
    values map: the value whose action WRITES the marker is the 'present'
    value; the value whose action DELETES the marker is the 'absent' value.

    This makes marker polarity self-describing per configurable rather than a
    hardcoded human-approval assumption: the legacy human-approval
    shape (values.false => write_marker, values.true => delete_marker)
    yields present='false'/absent='true', while the flipped tdd-autonomous
    shape (values.true => write_marker, values.false => delete_marker)
    yields present='true'/absent='false'.

    Returns (None, None) when the values map does not declare both a
    write_marker and a delete_marker action, leaving the caller to fall back
    to the legacy default.
    """
    values = configurable.get("values") or {}
    present = absent = None
    for label, mutation in values.items():
        if not isinstance(mutation, dict):
            continue
        api = mutation.get("api")
        if api == "write_marker":
            present = label
        elif api == "delete_marker":
            absent = label
    return present, absent


def _resolve_marker_value(repo_root: str, configurable: dict) -> str:
    """Resolve a marker-file configurable's current user-facing value by
    presence on disk, with polarity derived from the configurable's own
    values map: present -> the write_marker value, absent -> the
    delete_marker value.

    Falls back to the legacy human-approval polarity (present -> 'false',
    absent -> 'true') only when the values map does not declare both a
    write_marker and a delete_marker action.
    """
    storage = configurable.get("storage") or {}
    path = storage.get("path")
    if not path:
        return ""
    present_value, absent_value = _marker_polarity(configurable)
    if present_value is None or absent_value is None:
        present_value, absent_value = "false", "true"
    is_present = os.path.isfile(os.path.join(repo_root, path))
    return present_value if is_present else absent_value


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
        return _resolve_marker_value(repo_root, configurable)
    if stype == "json-key":
        raw = _resolve_json_key_value(repo_root, storage, default)
        return _reverse_map_json_value(raw, configurable)
    # json-array / json-array-templated are action-style; no scalar value
    return None


def emit_configurable_alert(feature_name: str, configurable_id: str,
                            *, repo_root: str) -> dict:
    """Resolve a single configurable by feature_name + configurable_id on
    the live per-feature path, evaluate its current value against alert-on,
    return print_result on match, ok_result on miss, or error_result when
    feature/configurable/alert-message cannot be resolved.

    Inv 54 — suppressed under auto-evolve: when .rabbit-auto-evolve-active is
    present, this live per-feature alert is a no-op (ok_result) before any
    resolution work. During autonomous mode the auto-evolve composite banner
    (emit_auto_evolve_banner / emit_auto_evolve_stop_line, Inv 55) is the
    single replacement surface, so the per-feature override alert must not
    double up on it.
    """
    if _auto_evolve_active(repo_root):
        return ok_result()
    fj = os.path.join(repo_root, ".claude", "features", feature_name,
                       "feature.json")
    if not os.path.isfile(fj):
        return error_result(f"feature {feature_name!r} not found: {fj}")
    try:
        with open(fj) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return error_result(f"feature.json unreadable for {feature_name!r}: {e}")
    if not isinstance(data, dict):
        return error_result(f"feature.json for {feature_name!r} is not a dict")
    configuration = data.get("configuration")
    if not isinstance(configuration, list):
        return error_result(
            f"configurable {configurable_id!r} not found in {feature_name!r}")
    cfg = None
    for entry in configuration:
        if isinstance(entry, dict) and entry.get("id") == configurable_id:
            cfg = entry
            break
    if cfg is None:
        return error_result(
            f"configurable {configurable_id!r} not found in {feature_name!r}")
    alert_msg = cfg.get("alert-message")
    if not isinstance(alert_msg, dict):
        return error_result(
            f"configurable {configurable_id!r} in {feature_name!r} has no alert-message")
    current = _resolve_current_value(repo_root, cfg)
    if current is None or current != cfg.get("alert-on"):
        return ok_result()
    return print_result(alert_msg["text"], alert_msg["icon"], alert_msg["color"])


# Filename pattern produced by build-prompt.py:
#   <id>-<pid>-<YYYYMMDD>-<HHMMSS>-<ms>.txt
_PROMPT_FILENAME_TS_RE = re.compile(
    r"^.+-\d+-(\d{8})-(\d{6})-\d+\.txt$"
)


def cleanup_old_prompts(max_age_days: int, *, repo_root: str) -> dict:
    """Walk <repo_root>/.rabbit/prompts/ and delete .txt files older than
    max_age_days based on the embedded YYYYMMDD-HHMMSS-ms timestamp in the
    filename (deterministic — no stat() call). Files whose names don't
    match the build-prompt.py pattern are skipped (not deleted).
    Non-.txt files (e.g. .injection-failures.log) are ignored. Returns
    ok_result on success or when the directory doesn't exist. Idempotent:
    re-running after cleanup is a no-op that still returns ok_result.
    """
    prompts_dir = os.path.join(repo_root, ".rabbit", "prompts")
    if not os.path.isdir(prompts_dir):
        return ok_result()
    cutoff = time.time() - max_age_days * 86400
    for name in os.listdir(prompts_dir):
        if not name.endswith(".txt"):
            continue
        m = _PROMPT_FILENAME_TS_RE.match(name)
        if not m:
            continue
        ts_str = f"{m.group(1)}-{m.group(2)}"
        try:
            t = time.mktime(time.strptime(ts_str, "%Y%m%d-%H%M%S"))
        except ValueError:
            continue
        if t < cutoff:
            try:
                os.remove(os.path.join(prompts_dir, name))
            except OSError:
                pass
    return ok_result()


def check_prompt_injection_failures(log_path: str, *, repo_root: str) -> dict:
    """Read the PreToolUse prompt-injector failure log at log_path
    (repo-root-relative). Each line is a JSON object
    {ts, skill, callable_id, error}. When the log has entries, return a
    red print_result summarizing the distinct failing skill names and
    EMPTY the log file (consume pattern matching check_marker_consume_alert).
    When empty or missing, return ok_result.
    """
    full = os.path.join(repo_root, log_path)
    if not os.path.isfile(full):
        return ok_result()
    try:
        with open(full) as f:
            raw = f.read()
    except OSError as e:
        return error_result(f"prompt-injection log unreadable: {e}")
    if not raw.strip():
        return ok_result()

    seen = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        skill = entry.get("skill") if isinstance(entry, dict) else None
        if skill and skill not in seen:
            seen.append(skill)

    if not seen:
        # Log had non-empty content but no recoverable skill names;
        # still empty the log so we don't loop.
        try:
            open(full, "w").close()
        except OSError:
            pass
        return ok_result()

    names = ", ".join(seen)
    text = f"prompt-injection failures: {names}"
    try:
        open(full, "w").close()
    except OSError:
        pass
    return print_result(text, "📢", "red")


def write_mode_marker(*, repo_root: str) -> dict:
    """SessionStart helper that bridges rabbit-meta mode detection into the
    rabbit-cage dispatcher protocol. Lazy-imports
    rabbit-meta.lib.mode_detection.detect_mode from
    <repo_root>/.claude/features/rabbit-meta/lib/mode_detection.py, calls
    detect_mode(os.getcwd()), ensures <repo_root>/.rabbit/.runtime/ exists,
    writes the resulting "plugin" or "standalone" string to
    <repo_root>/.rabbit/.runtime/mode.

    Idempotent: re-running with unchanged content is a no-op (content-equality
    check before write — preserves mtime when the mode hasn't changed).

    Returns ok_result on success, error_result("rabbit-meta unavailable") when
    rabbit-meta cannot be imported (degenerate self-build scenario), or
    error_result(message) on filesystem failure.
    """
    mode_path = os.path.join(repo_root, ".claude", "features",
                              "rabbit-meta", "lib", "mode_detection.py")
    try:
        spec = importlib.util.spec_from_file_location(
            "rabbit_meta_mode_detection", mode_path)
        if spec is None or spec.loader is None:
            return error_result("rabbit-meta unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        detect_mode = module.detect_mode
    except (FileNotFoundError, ImportError, AttributeError):
        return error_result("rabbit-meta unavailable")

    try:
        mode = detect_mode(os.getcwd())
        target_dir = os.path.join(repo_root, ".rabbit", ".runtime")
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, "mode")
        if os.path.isfile(target):
            try:
                with open(target) as f:
                    if f.read() == mode:
                        return ok_result()
            except OSError:
                pass
        with open(target, "w") as f:
            f.write(mode)
        return ok_result()
    except OSError as e:
        return error_result(str(e))


def _load_rabbit_block(repo_root: str):
    """Lazy-load rabbit_block from contract/scripts/rabbit_print.py.

    The script directory is not on sys.path by default; we resolve it
    relative to repo_root and import via importlib.
    """
    path = os.path.join(repo_root, ".claude", "features", "contract",
                         "scripts", "rabbit_print.py")
    spec = importlib.util.spec_from_file_location("rabbit_print_runtime", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load rabbit_print from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.rabbit_block


def check_release_update(*, repo_root: str) -> dict:
    """Thin runtime wrapper around scripts/check-release-update.py.

    Subprocesses the helper (which owns the throttle, urllib fetch, and
    version compare per Inv 53), parses its JSON stdout, and translates
    the result into a typed runtime return:

      - {"newer": true, ...}  -> print_result(text, "📦", "yellow") where
        text is a rabbit_block of three lines: update headline, the
        install.py --update command (or fresh-install fallback when
        self_update_available is false), and the `claude --resume` hint.
      - {"newer": false}      -> ok_result()
      - any other outcome (non-zero exit, empty stdout, malformed JSON,
        subprocess exception) -> ok_result() silently. NEVER blocks or
        surfaces errors to Claude.

    Per spec Inv 39, this function contains NO HTTP, version-compare, or
    throttle logic — that all lives in the helper script.
    """
    script = os.path.join(repo_root, ".claude", "features", "contract",
                           "scripts", "check-release-update.py")
    try:
        env = os.environ.copy()
        env["RABBIT_ROOT"] = repo_root
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=15, env=env,
        )
    except Exception:  # noqa: BLE001 - NEVER block the user
        return ok_result()

    if result.returncode != 0:
        return ok_result()
    raw = (result.stdout or "").strip()
    if not raw:
        return ok_result()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ok_result()
    if not isinstance(payload, dict) or not payload.get("newer"):
        return ok_result()

    channel = payload.get("channel", "?")
    current = payload.get("current", "?")
    new = payload.get("new", "?")
    self_update = bool(payload.get("self_update_available"))

    try:
        rabbit_block = _load_rabbit_block(repo_root)
    except (ImportError, OSError):
        return ok_result()

    headline = f"update available: {new} (current: {current}) on channel {channel}"
    if self_update:
        update_line = "to update: cd <project-root> && python3 .rabbit/install.py --update"
    else:
        update_line = "to update: see README for first-install command"
    resume_line = "then resume: claude --resume"
    text = rabbit_block(headline, update_line, resume_line)
    return print_result(text, "📦", "yellow")


def emit_auto_evolve_banner(*, repo_root: str) -> list:
    """Inv 55 — composite SessionStart banner for rabbit-auto-evolve.

    Returns [] when .rabbit-auto-evolve-active is absent (the marker gates the
    entire auto-evolve composite surface). When active, delegates the line-1
    and line-2 content to rabbit-auto-evolve/scripts/banner-status.py via
    subprocess. Contract owns the dispatch mechanism (gate, script-path
    resolution, subprocess invocation, JSON parse, mapping to print_result);
    rabbit-auto-evolve owns the per-variant content (text/icon/color).

    Returns [] on any failure mode (script missing, non-zero exit, parse
    error, active:false in JSON, missing line1/line2 keys) — the banner is
    best-effort and MUST NEVER crash the SessionStart dispatcher.
    """
    if not _auto_evolve_active(repo_root):
        return []
    script_path = os.path.join(
        repo_root,
        ".claude/features/rabbit-auto-evolve/scripts/banner-status.py",
    )
    if not os.path.exists(script_path):
        return []
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            env={**os.environ, "RABBIT_AUTO_EVOLVE_REPO_ROOT": repo_root},
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    try:
        parsed = json.loads(result.stdout)
    except (ValueError, TypeError):
        return []
    if parsed.get("active") is not True:
        return []
    try:
        line1 = parsed["line1"]
        line2 = parsed["line2"]
        return [
            print_result(line1["text"], line1["icon"], line1["color"]),
            print_result(line2["text"], line2["icon"], line2["color"]),
        ]
    except (KeyError, TypeError):
        return []


# Inv 55 stop-line priority order: aborted > restart-needed > stop-requested >
# running. The first matching state marker wins; later entries are dead-letter.
_AUTO_EVOLVE_STOP_LINE_MARKERS = (
    (".rabbit-auto-evolve-aborted",
     "auto-evolve loop aborted — see .rabbit/auto-evolve-state.json",
     "⛔", "red"),
    (".rabbit-auto-evolve-restart-needed",
     "auto-evolve loop awaiting restart",
     "⏸", "yellow"),
    (".rabbit-auto-evolve-stop-requested",
     "auto-evolve loop stop requested — will exit on next tick",
     "⏸", "yellow"),
    (".rabbit-auto-evolve-running",
     "auto-evolve loop running",
     "🔁", "green"),
)

# Inv 55 steady active/idle line: emitted when .rabbit-auto-evolve-active is
# present, none of the four short-lived state markers is, AND the loop has been
# started at least once (.rabbit/auto-evolve-state.json exists). This is the
# dominant steady state (active loop between ticks).
_AUTO_EVOLVE_STOP_LINE_IDLE = (
    "auto-evolve loop active — idle between ticks", "🔁", "green",
)

# Inv 55 restart-pending line: emitted when .rabbit-auto-evolve-active is
# present, none of the four short-lived state markers is, AND the loop has NEVER
# been started — detected by the ABSENCE of .rabbit/auto-evolve-state.json
# (only rabbit-auto-evolve's start-loop.py creates it on the first `start`).
# set-evolve-mode.py `on` writes the activation markers but NOT the state file,
# so the post-`on`/pre-`start` window lands here: configured but not yet running,
# with a restart pending. Reusable by rabbit-auto-evolve's banner-status.py so
# the SessionStart banner agrees verbatim.
_AUTO_EVOLVE_STOP_LINE_RESTART_PENDING = (
    "auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start",
    "⏸", "yellow",
)


def _auto_evolve_ever_started(repo_root: str) -> bool:
    """True iff .rabbit/auto-evolve-state.json exists at repo root — the
    signal that rabbit-auto-evolve's start-loop.py has bootstrapped the loop
    at least once. Its absence marks the post-`on`/pre-`start` window.
    """
    return os.path.isfile(
        os.path.join(repo_root, ".rabbit", "auto-evolve-state.json"))


def _parse_cron_minutes(field: str) -> set:
    """Parse a crontab MINUTE field into the set of minutes (0..59) it fires
    on. Supports the cadence forms the heartbeat actually uses: ``*`` (every
    minute), comma lists (``13,43``), and step expressions (``*/15``).
    Returns an empty set for any minute it cannot parse (caller treats empty
    as "no parseable cron")."""
    field = field.strip()
    if field == "*":
        return set(range(60))
    if field.startswith("*/"):
        try:
            step = int(field[2:])
        except ValueError:
            return set()
        if step <= 0:
            return set()
        return set(range(0, 60, step))
    minutes = set()
    for part in field.split(","):
        part = part.strip()
        if not part.isdigit():
            return set()
        m = int(part)
        if not 0 <= m <= 59:
            return set()
        minutes.add(m)
    return minutes


# rabbit-auto-evolve-owned artifact carrying the empirical CronCreate jitter
# offset (Inv 56). Declared in this feature's contract.md reads.files; contract
# READS observed_jitter_minutes without importing rabbit-auto-evolve.
_AUTO_EVOLVE_TICK_JITTER_FILE = os.path.join(".rabbit", "auto-evolve-tick-jitter.json")


def _cadence_period_minutes(minutes: set) -> int:
    """The cadence period: the smallest gap (mod 60) between consecutive fire
    minutes. A single fire minute per hour is a 60-min period. Mirrors
    rabbit-auto-evolve banner-status.py._period_minutes so the cold-start
    fallback offset matches byte-for-byte.
    """
    if not minutes:
        return 0
    ordered = sorted(minutes)
    if len(ordered) == 1:
        return 60
    gaps = []
    for i in range(len(ordered)):
        gap = (ordered[(i + 1) % len(ordered)] - ordered[i]) % 60
        if gap == 0:
            gap = 60
        gaps.append(gap)
    return min(gaps)


def _auto_evolve_jitter_offset_minutes(repo_root: str, period_minutes: int) -> int:
    """The deterministic CronCreate per-job jitter offset (Inv 56) to ADD to
    the next cron boundary. Reads ``observed_jitter_minutes`` from the
    rabbit-auto-evolve-owned artifact ``.rabbit/auto-evolve-tick-jitter.json``
    (a contract-bound cross-feature read declared in contract.md reads.files).
    When the artifact is absent, unreadable, or carries no usable non-negative
    integer, falls back to the documented cold-start bound
    ``min(15, ceil(period_minutes * 0.10))`` — exactly as rabbit-auto-evolve's
    banner-status.py does, so the SessionStart banner and the Stop line render
    the same value.
    """
    path = os.path.join(repo_root, _AUTO_EVOLVE_TICK_JITTER_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            val = data.get("observed_jitter_minutes")
            if isinstance(val, int) and val >= 0:
                return val
    except (OSError, ValueError):
        pass
    if period_minutes <= 0:
        return 0
    return min(15, math.ceil(period_minutes * 0.10))


def _auto_evolve_next_tick_eta(repo_root: str, now) -> str:
    """Compute the next rabbit-auto-evolve heartbeat fire as a SINGLE bare
    EXACT-TIME ``"HH:MM"`` string — the next cron boundary at/after the injected
    ``now`` PLUS the deterministic CronCreate per-job jitter offset (Inv 56).
    A single bare wall-clock time: no lower-bound sign, no range, no qualifier.

    Reads the durable heartbeat cadence from
    ``<repo_root>/.claude/scheduled_tasks.json`` — the ``tasks[]`` entry whose
    ``prompt`` references ``rabbit-auto-evolve``. Only the cron MINUTE field is
    matched against an unrestricted (``*``) HOUR, which is the cadence shape
    the heartbeat uses (``13,43 * * * *``); the boundary is the next wall-clock
    minute in that minute-set, wrapping to the next hour (and across midnight)
    as needed.

    #881 (third reopen): CronCreate adds a deterministic per-job jitter to
    recurring tasks — they fire late by a stable per-job offset (observed
    CONSTANT +13 min on the 30-min ``13,43`` heartbeat, on an IDLE session;
    scheduled prompts fire only while the REPL is idle, never mid-query). The
    displayed time is therefore boundary + offset, where the offset is READ
    from the rabbit-auto-evolve-owned artifact
    ``.rabbit/auto-evolve-tick-jitter.json`` (``observed_jitter_minutes``), with
    a cold-start fallback ``min(15, ceil(period_minutes * 0.10))`` when the
    artifact is absent. The value mirrors the rabbit-auto-evolve
    ``banner-status.py`` ``next tick HH:MM`` string byte-for-byte so the
    SessionStart banner and the Stop line read consistently.

    Returns ``None`` on any of: missing file, unreadable file, JSON parse
    error, no matching task, or no parseable cron minutes — so the caller
    degrades to the bare idle line rather than rendering a fabricated ETA.
    """
    path = os.path.join(repo_root, ".claude", "scheduled_tasks.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    cron = None
    for task in data.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        if "rabbit-auto-evolve" in str(task.get("prompt", "")):
            cron = task.get("cron")
            break
    if not isinstance(cron, str):
        return None
    parts = cron.split()
    if len(parts) < 1:
        return None
    minutes = _parse_cron_minutes(parts[0])
    if not minutes:
        return None
    # Walk forward minute-by-minute from now+1 until a fire minute is hit.
    # Bounded by 24h (1440 minutes) — always terminates since minutes is
    # non-empty and the hour field is treated as unrestricted.
    candidate = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    for _ in range(1440):
        if candidate.minute in minutes:
            offset = _auto_evolve_jitter_offset_minutes(
                repo_root, _cadence_period_minutes(minutes))
            fire = candidate + datetime.timedelta(minutes=offset)
            return fire.strftime("%H:%M")
        candidate += datetime.timedelta(minutes=1)
    return None


def emit_auto_evolve_stop_line(*, repo_root: str, now=None) -> list:
    """Inv 55 — composite Stop-hook line for rabbit-auto-evolve.

    Returns [] only when .rabbit-auto-evolve-active is absent (the marker
    gates the entire auto-evolve composite surface). When active, returns
    exactly one print_result entry: a state marker chosen by the strict
    priority order aborted > restart-needed > stop-requested > running when one
    is present, otherwise (no state marker) the restart-pending line when the
    loop has never been started (.rabbit/auto-evolve-state.json absent) or
    the steady active/idle line when it has (active loop between ticks),
    symmetric with emit_auto_evolve_banner.

    Only the steady idle line is extended with a single bare EXACT-TIME
    next-tick ETA ("auto-evolve loop active — idle, next tick HH:MM") when the
    heartbeat cadence at .claude/scheduled_tasks.json is present and parseable;
    it degrades to the bare idle text otherwise. The displayed HH:MM is the
    next cron boundary plus the deterministic CronCreate per-job jitter offset
    (Inv 56), read from .rabbit/auto-evolve-tick-jitter.json (cold-start bound
    when absent) — matching rabbit-auto-evolve's banner-status.py "next tick
    HH:MM" string byte-for-byte. The `now` argument is the injected wall-clock
    used solely for that ETA (default None -> real clock); it changes no
    marker/state-file logic. The four priority-marker lines and the
    restart-pending line never carry an ETA.
    """
    if not _auto_evolve_active(repo_root):
        return []
    for path, text, icon, color in _AUTO_EVOLVE_STOP_LINE_MARKERS:
        if os.path.isfile(os.path.join(repo_root, path)):
            return [print_result(text=text, icon=icon, color=color)]
    if _auto_evolve_ever_started(repo_root):
        _, icon, color = _AUTO_EVOLVE_STOP_LINE_IDLE
        if now is None:
            now = datetime.datetime.now()
        eta = _auto_evolve_next_tick_eta(repo_root, now)
        if eta is not None:
            text = f"auto-evolve loop active — idle, next tick {eta}"
        else:
            text = _AUTO_EVOLVE_STOP_LINE_IDLE[0]
    else:
        text, icon, color = _AUTO_EVOLVE_STOP_LINE_RESTART_PENDING
    return [print_result(text=text, icon=icon, color=color)]


def emit_stop_timestamp(*, repo_root: str, now=None) -> list:
    """Inv 57 — universal Stop-event turn-end timestamp.

    Returns exactly one print_result entry whose text is the current LOCAL
    wall-clock time formatted as ``"%H:%M:%S %Z"`` (e.g. ``"03:32:07 EDT"``),
    icon ⏱, color green. The clock is LOCAL, not UTC: the idle Stop-line
    next-tick ETA (Inv 55, via ``_auto_evolve_next_tick_eta``) and the
    SessionStart banner ETA both render local wall-clock, and the heartbeat
    cron fires in local time — so a UTC clock next to a local ETA would read
    as hours in the past. Rendering local with an explicit tz label keeps the
    whole composite Stop-line consistent and unambiguous.

    Reads no markers, no files, no env vars; ``repo_root`` is accepted for
    dispatcher-signature consistency but unused. The optional ``now`` is an
    injected AWARE ``datetime`` used solely for deterministic test rendering
    (default ``None`` → the real local clock via
    ``datetime.datetime.now().astimezone()``, an aware local datetime so
    ``%Z`` populates with the real zone abbreviation). NEVER short-circuits
    to [] — every invocation emits the timestamp line so every Stop event in
    every session has a turn-end marker visible regardless of auto-evolve
    mode.

    The single entry is tagged with the footer-ordering marker
    ``"order": "footer"``. ``order`` is an optional
    payload-level rendering hint whose only defined value is ``"footer"``;
    absence (the default for every other producer) means normal order. A
    payload carrying ``"order": "footer"`` instructs the rabbit-cage
    dispatcher's ``render_emission`` to render that line AFTER all
    non-footer lines, so the passive turn-end marker deterministically
    closes the Stop block instead of being pushed above actionable status
    lines emitted by alphabetically-later features. The
    print_result/banner_result/subline_result factories are unchanged —
    they never set ``order``; only this function adds it (by dict-merge).
    """
    if now is None:
        now = datetime.datetime.now().astimezone()
    text = now.strftime("%H:%M:%S %Z")
    return [{**print_result(text, "⏱", "green"), "order": "footer"}]
