"""_dispatcher_lib.py — shared helper for rabbit-cage event dispatchers.

The three event-dispatcher hooks (stop-dispatcher.py,
session-start-dispatcher.py, user-prompt-submit-dispatcher.py) each
call into this module to enumerate features, invoke runtime APIs
declared in each feature's `feature.json runtime[<event>]`, partition
the typed results, and render one Claude Code JSON object per event.

Public API:
    enumerate_features(repo_root) -> Iterator[(name, feature_dir, feature_dict)]
    dispatch_event(event, repo_root) -> List[dict]
    render_emission(payloads) -> Optional[dict]

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code exposes native per-event
    dispatchers that subsume rabbit-cage's event-dispatcher hooks.
"""

import inspect
import json
import os
import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, *_HERE.parents]:
    _contract = _candidate / "features" / "contract"
    if (_contract / "lib" / "runtime.py").is_file():
        if str(_contract) not in sys.path:
            sys.path.insert(0, str(_contract))
        break
for _candidate in [_HERE, *_HERE.parents]:
    _scripts = _candidate / "features" / "contract" / "scripts"
    if (_scripts / "rabbit_print.py").is_file():
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        break

from lib import runtime as _runtime  # noqa: E402
from rabbit_print import rabbit_block, rabbit_print, rabbit_subline  # noqa: E402


def enumerate_features(repo_root):
    """Yield (name, feature_dir, feature_dict) for each active feature.

    Walks <repo_root>/.claude/features/*/feature.json in alphabetical
    order by directory name. Skips:
      - directories with no feature.json
      - feature.json files whose JSON parse fails
      - features whose top-level `status` == "retired"
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
        if data.get("status") == "retired":
            continue
        yield name, fdir, data


def _invoke(fn, args, *, feature_dir, repo_root):
    sig = inspect.signature(fn)
    kwargs = dict(args)
    if "repo_root" in sig.parameters:
        kwargs["repo_root"] = repo_root
    if "feature_dir" in sig.parameters:
        kwargs["feature_dir"] = feature_dir
    return fn(**kwargs)


def dispatch_event(event, repo_root):
    """Iterate every active feature; invoke each entry in its
    runtime[event] array via contract.lib.runtime. Returns a flat list
    of result dicts (each {"type": "print"|"inject"|"ok"|"error", ...}).

    Iteration order: alphabetical by feature name, then declaration order
    within each feature's runtime[event] array.
    """
    payloads = []
    for _name, fdir, data in enumerate_features(repo_root):
        runtime_decls = data.get("runtime") or {}
        entries = runtime_decls.get(event) or []
        for entry in entries:
            api_name = entry.get("api", "")
            args = entry.get("args") or {}
            fn = getattr(_runtime, api_name, None)
            if fn is None:
                payloads.append(_runtime.error_result(
                    f"unknown runtime API: {api_name!r}"))
                continue
            try:
                result = _invoke(fn, args, feature_dir=fdir, repo_root=repo_root)
            except Exception as e:  # noqa: BLE001 — dispatcher catches faults
                payloads.append(_runtime.error_result(
                    f"{api_name} raised: {e}"))
                continue
            if isinstance(result, list):
                payloads.extend(result)
            else:
                payloads.append(result)
    return payloads


def render_emission(payloads):
    """Partition payloads and assemble the final Claude Code JSON dict.

    banner -> rendered via rabbit_print(text, icon, color, format='banner')
              (decorated with ━━━ bars).
    print  -> rendered via rabbit_subline(text, color, icon) (compact format).
    subline-> rendered via rabbit_subline(text, color) without icon.
    inject -> concatenated into additionalContext.
    ok     -> dropped.
    error  -> written to stderr (one line per error); not surfaced.

    Returns None when no renderable lines and no inject are present.
    """
    lines = []
    injects = []
    for p in payloads:
        t = p.get("type")
        if t == "banner":
            lines.append(rabbit_print(p["text"], p["icon"], p["color"], format="banner"))
        elif t == "print":
            lines.append(rabbit_subline(p["text"], color=p["color"], icon=p["icon"]))
        elif t == "subline":
            lines.append(rabbit_subline(p["text"], color=p.get("color", "green")))
        elif t == "inject":
            injects.append(p)
        elif t == "error":
            sys.stderr.write(f"dispatcher: {p.get('message', '')}\n")
        # 'ok' and unknown: drop
    if not lines and not injects:
        return None
    out = {}
    if lines:
        out["systemMessage"] = rabbit_block(*lines)
    if injects:
        out["additionalContext"] = "".join(p["content"] for p in injects)
    return out
