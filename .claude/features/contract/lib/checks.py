"""contract.lib.checks — library API for contract enforcement / validation.

Holds the logic that used to live in each scripts/enforcement/check-*.py
and scripts/validate-feature.py. Each function returns a CheckResult; no
function calls sys.exit, prints, or raises on contract-violation conditions.

Per spec Inv 37.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when a native rabbit CLI exposes equivalent bindings.
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List


@dataclass
class CheckResult:
    """Outcome of a single check.

    passed   - True iff the check found no violations.
    messages - Human-readable lines (one per issue or summary line).
    """

    passed: bool
    messages: List[str] = field(default_factory=list)


# ---------- shared helpers ----------------------------------------------------

def get_repo_root():
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# ---------- check_tests_non_interactive --------------------------------------

_INTERACTIVE_PATTERNS = [
    (re.compile(r'(?<![A-Za-z0-9_.])input\s*\('), "bare input() call"),
    (re.compile(r'getpass\s*\.\s*getpass\s*\('), "getpass.getpass()"),
    (re.compile(r'click\s*\.\s*prompt\s*\('), "click.prompt()"),
    (re.compile(r'click\s*\.\s*confirm\s*\('), "click.confirm()"),
]


def _strip_comments(code: str) -> str:
    lines = code.splitlines()
    filtered = [line for line in lines if not re.match(r'^\s*#', line)]
    return "\n".join(filtered)


def check_tests_non_interactive(feature_dir: str) -> CheckResult:
    """Inv 13: <feature-dir>/test/*.py must not use interactive constructs."""
    test_dir = os.path.join(feature_dir, "test")
    if not os.path.isdir(test_dir):
        return CheckResult(True, [f"OK: no test/ in {feature_dir} (vacuous)"])
    messages: List[str] = []
    for dirpath, _, filenames in os.walk(test_dir):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath) as f:
                raw = f.read()
            code = _strip_comments(raw)
            for pattern, desc in _INTERACTIVE_PATTERNS:
                if pattern.search(code):
                    messages.append(f"VIOLATION: {fpath} uses {desc}.")
                    break
    if messages:
        messages.append(f"FAIL: {len(messages)} interactive construct(s) found in {test_dir}.")
        return CheckResult(False, messages)
    return CheckResult(True, [f"OK: no interactive constructs in {test_dir}"])


# ---------- check_sentinel ---------------------------------------------------

_SENTINEL = "RABBIT-POLICY-BLOCK-v1"


def check_sentinel(path: str) -> CheckResult:
    """Inv 20: dispatch scripts must contain the policy-block sentinel."""
    if not os.path.exists(path):
        return CheckResult(False, [f"ERROR: not a file or directory: {path}"])
    missing: List[str] = []
    if os.path.isfile(path):
        with open(path) as f:
            if _SENTINEL not in f.read():
                missing.append(f"MISSING sentinel in: {path}")
    else:
        for dirpath, _, filenames in os.walk(path):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                with open(fpath) as f:
                    if _SENTINEL not in f.read():
                        missing.append(f"MISSING sentinel in: {fpath}")
    if missing:
        return CheckResult(False, missing)
    return CheckResult(True, [f"OK: sentinel present in {path}"])


# ---------- check_naming -----------------------------------------------------

_BANNED_PREFIXES = ["rbt-"]


def check_naming(root: str) -> CheckResult:
    """Inv 10 + Inv 15: artifact names start with 'rabbit-'; 'rbt-' is banned."""
    if not os.path.isdir(root):
        return CheckResult(False, [f"ERROR: not a directory: {root}"])
    claude_dir = os.path.join(root, ".claude")
    if not os.path.isdir(claude_dir):
        return CheckResult(True, [f"OK: no .claude tree at {root} (vacuous)"])

    messages: List[str] = []
    flagged = set()

    def flag(label: str, name: str, path: str, reason: str) -> None:
        if path in flagged:
            return
        flagged.add(path)
        messages.append(f"VIOLATION: {label} {path} — {reason} ('{name}')")

    for sub, label in (("commands", "command"), ("agents", "agent")):
        d = os.path.join(claude_dir, sub)
        if os.path.isdir(d):
            for fname in os.listdir(d):
                if not fname.endswith(".md"):
                    continue
                base = fname[:-3]
                if base in ("README", "CHANGELOG"):
                    continue
                if not base.startswith("rabbit-"):
                    flag(label, base, os.path.join(d, fname), "must start with 'rabbit-'")

    skills_dir = os.path.join(claude_dir, "skills")
    if os.path.isdir(skills_dir):
        for entry in os.listdir(skills_dir):
            full = os.path.join(skills_dir, entry)
            if not os.path.isdir(full):
                continue
            if not entry.startswith("rabbit-"):
                flag("skill", entry, full + "/", "must start with 'rabbit-'")

    docs_path = os.path.join(claude_dir, "docs")
    for dirpath, dirnames, filenames in os.walk(claude_dir):
        if os.path.abspath(dirpath).startswith(os.path.abspath(docs_path)):
            dirnames.clear()
            continue
        for fname in filenames:
            for bad in _BANNED_PREFIXES:
                if fname.startswith(bad):
                    flag("file", fname, os.path.join(dirpath, fname),
                         f"deprecated '{bad}' prefix banned (use 'rabbit-' or no prefix)")
                    break

    if messages:
        messages.append(f"FAIL: {len(messages)} naming violation(s) under {claude_dir}")
        return CheckResult(False, messages)
    return CheckResult(True, [
        f"OK: all artifacts under {claude_dir} start with 'rabbit-'; "
        f"no banned prefixes ({_BANNED_PREFIXES}) outside docs/"
    ])


# ---------- check_imports_resolve --------------------------------------------

_AT_REL_RE = re.compile(r'@\./([^\s]+)')
_CLAUDE_PATH_RE = re.compile(
    r'\.claude/(?:features|hooks|skills|commands|agents)/[a-z][a-z0-9-]+'
    r'(?:/[^\s`)\]\'",]+)?'
)


def check_imports_resolve(feature_dir: str) -> CheckResult:
    """Inv 25: every @<path> import and .claude/<surface>/<name> path in docs/*.md resolves."""
    docs_dir = os.path.join(feature_dir, "docs")
    if not os.path.isdir(docs_dir):
        return CheckResult(True, [f"OK: no docs/ in {feature_dir} (vacuous)"])
    repo_root = get_repo_root()
    if not repo_root:
        return CheckResult(False, ["ERROR: cannot determine repo root"])

    messages: List[str] = []
    for root, _, files in os.walk(docs_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(root, fname)
            if "/archive/" in filepath:
                continue
            with open(filepath) as f:
                content = f.read()
            for match in _AT_REL_RE.finditer(content):
                path = match.group(1)
                if "{{" in path:
                    continue
                if not os.path.exists(os.path.join(repo_root, path)):
                    messages.append(f"MISSING: {path} (in {filepath})")
            for match in _CLAUDE_PATH_RE.finditer(content):
                path = match.group(0)
                if "{{" in path:
                    continue
                if not os.path.exists(os.path.join(repo_root, path)):
                    messages.append(f"MISSING: {path} (in {filepath})")
    if messages:
        messages.append("FAIL: one or more import/path references are missing")
        return CheckResult(False, messages)
    return CheckResult(True, ["OK: all import and feature path references resolve"])


# ---------- check_symlinks_resolve -------------------------------------------

def check_symlinks_resolve(root: str) -> CheckResult:
    """Inv 24: no dangling symlinks under <root>/.claude/."""
    claude_dir = os.path.join(root, ".claude")
    if not os.path.isdir(claude_dir):
        return CheckResult(True, [f"OK: no .claude/ at {root} (vacuous)"])
    dangling: List[str] = []
    for dirpath, dirnames, filenames in os.walk(claude_dir, followlinks=False):
        for fname in filenames + dirnames:
            full = os.path.join(dirpath, fname)
            if os.path.islink(full):
                target = os.path.realpath(full)
                if not target or not os.path.exists(target):
                    dangling.append(full)
    if dangling:
        messages = [f"DANGLING: {link}" for link in sorted(dangling)]
        messages.append(f"FAIL: dangling symlinks found under {root}/.claude")
        return CheckResult(False, messages)
    return CheckResult(True, ["OK: all symlinks under .claude/ resolve"])


# ---------- check_template_producer_consistency ------------------------------

# Inv 19: producer-field set MUST be derived from a live source, not hardcoded.
# Live source: bug.json.schema.json properties (the contract schema producers
# write against). Loaded lazily at module-load time from disk; if the schema
# is unreadable the set falls back to an empty set and the check fails loudly
# rather than silently passing.
_BUG_SCHEMA_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "schemas", "bug.json.schema.json",
))


def _load_producer_fields() -> set:
    try:
        with open(_BUG_SCHEMA_PATH) as f:
            schema = json.load(f)
        return set(schema.get("properties", {}).keys())
    except (OSError, json.JSONDecodeError):
        return set()


_PRODUCER_FIELDS = _load_producer_fields()
_TEMPLATE_METADATA = {"template_version"}


def check_template_producer_consistency(template_path: str) -> CheckResult:
    """Inv 19: template top-level keys are a subset of the live producer field set."""
    try:
        with open(template_path) as f:
            data = json.load(f)
    except Exception as e:
        return CheckResult(False, [f"ERROR: failed to parse {template_path}: {e}"])
    messages: List[str] = []
    for k in data.keys():
        if k in _TEMPLATE_METADATA:
            continue
        if k not in _PRODUCER_FIELDS:
            messages.append(
                f"UNKNOWN KEY: '{k}' in {template_path} is not in the producer field set"
            )
    if messages:
        messages.append("FAIL: template-schema-producer consistency check failed")
        return CheckResult(False, messages)
    return CheckResult(True, [
        "OK: all template keys are consistent with the live producer field set"
    ])


# ---------- check_numbered_lists ---------------------------------------------

_NUMBERED_PATTERNS = [
    (re.compile(r"^\s*#{1,6}\s+\d+\.\d+(?:\.\d+)*\b"), "heading-decimal"),
    (re.compile(r"^\s*#{1,6}\s+\d+[a-z]\b"), "heading-letter"),
    (re.compile(r"^\s*[-*+]?\s*\d+\.\d+(?:\.\d+)*\.\s"), "list-decimal"),
    (re.compile(r"^\s*[-*+]?\s*\d+[a-z][.):]\s"), "list-letter"),
]
_NUMBERED_SKIP = ("/archive/", "/docs/superpowers/")


def _numbered_is_skipped(path: str) -> bool:
    norm = path.replace(os.sep, "/")
    return any(s in norm for s in _NUMBERED_SKIP)


def _numbered_check_file(path: str) -> List[tuple]:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as e:
        return [(0, "read-error", str(e))]
    violations = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for rx, name in _NUMBERED_PATTERNS:
            if rx.match(line):
                violations.append((i, name, line.rstrip("\n")))
                break
    return violations


def _numbered_collect(target: str):
    if os.path.isfile(target):
        if target.endswith(".md") and not _numbered_is_skipped(target):
            yield target
        return
    for dirpath, dirnames, filenames in os.walk(target):
        if _numbered_is_skipped(dirpath + os.sep):
            dirnames[:] = []
            continue
        for fname in filenames:
            if fname.endswith(".md"):
                p = os.path.join(dirpath, fname)
                if not _numbered_is_skipped(p):
                    yield p


def check_numbered_lists(targets: List[str]) -> CheckResult:
    """Inv 33: reject decimal/letter-suffix numbering in Markdown ordered lists & headings."""
    messages: List[str] = []
    for target in targets:
        if not os.path.exists(target):
            messages.append(f"ERROR: not a file or directory: {target}")
            continue
        for md in _numbered_collect(target):
            for line_no, name, content in _numbered_check_file(md):
                messages.append(f"{md}:{line_no}: {name} {content}")
    if messages:
        return CheckResult(False, messages)
    return CheckResult(True, ["OK: no numbered-list violations"])


# ---------- check_invariant_monotonic_order ----------------------------------

# Features listed here are skipped by check_invariant_monotonic_order while
# their spec.md still has out-of-order invariant numbering. Remove an entry
# once the corresponding renumber cycle lands. The list is now empty:
#   - contract was pruned in CONTRACT-BACKLOG-31 (single section, monotonic
#     1..39 after gap-closing renumber).
#   - rabbit-feature was pruned when PR #162 merged (single Invariants section,
#     monotonic after Inv 28 relocation).
#   - rabbit-cage was pruned in RABBIT-CAGE-BACKLOG-30 (continuous monotonic
#     1..90 across all 7 Invariants sections).
# The check now fully validates every feature on disk without skips.
_MONOTONIC_KNOWN_ISSUES = []

_INVARIANTS_HEADING_RE = re.compile(r"^(##|###)\s+Invariants\b")
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+")
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s")


def check_invariant_monotonic_order(feature_dirs: List[str]) -> CheckResult:
    """Inv 38: each '## Invariants' / '### Invariants' section's top-level
    numbered items MUST appear in strictly increasing order.

    feature_dirs - iterable of feature directory paths. Features named in
    _MONOTONIC_KNOWN_ISSUES are skipped (pending renumber). Features without
    docs/spec/spec.md are also silently skipped.

    Returns CheckResult; messages include 'SKIP:' lines for skipped features
    and 'VIOLATION:' lines for any non-monotonic step.
    """
    messages: List[str] = []
    violations: List[str] = []

    for feat_dir in feature_dirs:
        feat_name = os.path.basename(os.path.realpath(feat_dir))
        if feat_name in _MONOTONIC_KNOWN_ISSUES:
            messages.append(
                f"SKIP: {feat_name} (in KNOWN_ISSUES — pending renumber)"
            )
            continue
        spec_path = os.path.join(feat_dir, "docs", "spec", "spec.md")
        if not os.path.isfile(spec_path):
            continue
        try:
            with open(spec_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError) as e:
            violations.append(f"VIOLATION: {feat_name}: cannot read spec.md: {e}")
            continue

        in_section = False
        section_header = None
        prev_num = 0
        in_fence = False
        for line in lines:
            stripped = line.strip()
            # track fenced code blocks so we don't count list-like content inside them
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # any heading ends or potentially opens a section
            if _ANY_HEADING_RE.match(line):
                if _INVARIANTS_HEADING_RE.match(line):
                    in_section = True
                    section_header = stripped
                    prev_num = 0
                else:
                    in_section = False
                    section_header = None
                    prev_num = 0
                continue
            if not in_section:
                continue
            m = _NUMBERED_ITEM_RE.match(line)
            if m:
                n = int(m.group(1))
                if n <= prev_num:
                    violations.append(
                        f"VIOLATION: {feat_name}:{section_header}: "
                        f"{prev_num} → {n} not monotonic"
                    )
                prev_num = n

    if violations:
        return CheckResult(False, messages + violations)
    if not messages:
        messages.append("OK: no feature dirs supplied (vacuous)")
    else:
        messages.append("OK: all checked features monotonic")
    return CheckResult(True, messages)


# ---------- validate_feature -------------------------------------------------

_VALID_TDD_STATES = {"spec", "spec-update", "test-red", "impl", "test-green",
                     "review", "merged", "deprecated"}


def validate_feature(feature_dir: str) -> CheckResult:
    """Validate a feature directory against the feature-skeleton schema.

    Returns CheckResult(passed=True, [...]) on success.
    Returns CheckResult(passed=False, [...]) on validation errors.
    Retired features (status=retired) short-circuit to passed=True with a
    RETIRED: notice (spec Inv 36b).
    """
    if not feature_dir:
        return CheckResult(False, ["ERROR: feature_dir is empty"])
    if not os.path.isdir(feature_dir):
        return CheckResult(False, [f"ERROR: not a directory: {feature_dir}"])

    expected_name = os.path.basename(os.path.realpath(feature_dir))
    errors: List[str] = []

    feature_json_path = os.path.join(feature_dir, "feature.json")

    # Inv 36b: retired feature short-circuit
    if os.path.isfile(feature_json_path):
        try:
            with open(feature_json_path) as f:
                early = json.load(f)
            if early.get("status") == "retired":
                return CheckResult(True, [
                    f"RETIRED: {feature_dir} (status=retired; structural checks skipped)"
                ])
        except (json.JSONDecodeError, OSError):
            pass

    def err(msg: str) -> None:
        errors.append(f"ERROR: {msg}")

    # Required files / dirs
    if not os.path.isfile(feature_json_path):
        err("missing feature.json")
    if not os.path.isfile(os.path.join(feature_dir, "docs", "spec", "spec.md")):
        err("missing docs/spec/spec.md")
    elif os.path.getsize(os.path.join(feature_dir, "docs", "spec", "spec.md")) == 0:
        err("docs/spec/spec.md is empty")
    if not os.path.isfile(os.path.join(feature_dir, "docs", "spec", "contract.md")):
        err("missing docs/spec/contract.md")
    elif os.path.getsize(os.path.join(feature_dir, "docs", "spec", "contract.md")) == 0:
        err("docs/spec/contract.md is empty")
    run_py = os.path.join(feature_dir, "test", "run.py")
    if not os.path.isfile(run_py):
        err("missing test/run.py")
    elif not os.access(run_py, os.X_OK):
        err("test/run.py not executable")

    if not os.path.isfile(feature_json_path):
        errors.append(f"FAIL: {len(errors)} error(s) in {feature_dir}")
        return CheckResult(False, errors)

    try:
        with open(feature_json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        err("feature.json is not valid JSON")
        errors.append(f"FAIL: {len(errors)} error(s) in {feature_dir}")
        return CheckResult(False, errors)

    # Schema validation (jsonschema optional dep)
    schema_path = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "schemas", "feature.json.schema.json",
    ))
    if os.path.isfile(schema_path):
        try:
            import jsonschema  # type: ignore
            with open(schema_path) as f:
                schema = json.load(f)
            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as e:
                err(f"feature.json: schema violation: {e.message}")
        except ImportError:
            pass

    name = data.get("name", "")
    if not name:
        err("feature.json: missing name")
    elif name != expected_name:
        err(f"feature.json: name '{name}' does not match directory name '{expected_name}'")

    version = data.get("version", "")
    if not version:
        err("feature.json: missing version")
    elif not re.match(r"^\d+\.\d+\.\d+$", version):
        err(f"feature.json: version '{version}' is not semver (X.Y.Z)")

    owner = data.get("owner", "")
    if not owner:
        err("feature.json: missing owner")
    elif isinstance(owner, dict):
        err("feature.json: owner must be a flat string, not an object")

    tdd_state = data.get("tdd_state", "")
    if not tdd_state:
        err("feature.json: missing tdd_state")
    elif tdd_state not in _VALID_TDD_STATES:
        err(f"feature.json: invalid tdd_state '{tdd_state}' "
            f"(allowed: {' | '.join(sorted(_VALID_TDD_STATES))})")

    if not data.get("summary", ""):
        err("feature.json: missing summary")

    surface = data.get("surface")
    if not isinstance(surface, dict):
        err("feature.json: surface must be an object")
    else:
        for key in ("hooks", "commands", "agents", "skills"):
            if not isinstance(surface.get(key), list):
                err(f"feature.json: surface.{key} must be an array")

    if not data.get("deprecation_criterion", ""):
        err("feature.json: missing deprecation_criterion")

    if errors:
        errors.append(f"FAIL: {len(errors)} error(s) in {feature_dir}")
        return CheckResult(False, errors)
    return CheckResult(True, [f"PASS: {feature_dir}"])


# ---------------------------------------------------------------------------
# Meta-contract validation: manifest, runtime, and configuration arms
# are validated independently; each section is optional in feature.json.
# ---------------------------------------------------------------------------

_PUBLISH_API_ENUM = frozenset({
    "publish_skill",
    "publish_command",
    "publish_agent",
    "publish_hook",
    "publish_settings",
    "publish_file",
    "publish_generated",
})


def _validate_manifest(manifest):
    """Validate a manifest declaration. Returns list of error message strings."""
    errors = []
    if not isinstance(manifest, list):
        errors.append(f"manifest must be an array, got {type(manifest).__name__}")
        return errors
    for i, item in enumerate(manifest):
        if not isinstance(item, dict):
            errors.append(f"manifest[{i}] must be an object, got {type(item).__name__}")
            continue
        if "api" not in item:
            errors.append(f"manifest[{i}] missing required 'api' field")
            continue
        if "args" not in item:
            errors.append(f"manifest[{i}] missing required 'args' field")
            continue
        if item["api"] not in _PUBLISH_API_ENUM:
            errors.append(f"manifest[{i}]: unknown publish api {item['api']!r} (valid: {sorted(_PUBLISH_API_ENUM)})")
        if not isinstance(item["args"], dict):
            errors.append(f"manifest[{i}].args must be an object, got {type(item['args']).__name__}")
        extra_keys = set(item.keys()) - {"api", "args"}
        if extra_keys:
            errors.append(f"manifest[{i}]: unexpected keys {sorted(extra_keys)} (only api and args allowed)")
    return errors


_RUNTIME_EVENT_ENUM = frozenset({"Stop", "SessionStart", "UserPromptSubmit", "PreToolUse"})

_RUNTIME_API_ENUM = frozenset({
    "check_drift_regenerate",
    "check_manifest_drift",
    "check_marker_alert",
    "check_marker_consume_alert",
    "check_counter_threshold_refresh",
    "welcome_with_policy",
    "iterate_configurables_alerts",
    "iterate_configurables_banner",
})


def _validate_runtime(runtime):
    """Validate a runtime declaration. Returns list of error message strings."""
    errors = []
    if not isinstance(runtime, dict):
        errors.append(f"runtime must be an object, got {type(runtime).__name__}")
        return errors
    for event, calls in runtime.items():
        if event not in _RUNTIME_EVENT_ENUM:
            errors.append(f"runtime: unknown event {event!r} (valid: {sorted(_RUNTIME_EVENT_ENUM)})")
            continue
        if not isinstance(calls, list):
            errors.append(f"runtime[{event!r}] must be an array, got {type(calls).__name__}")
            continue
        for i, item in enumerate(calls):
            if not isinstance(item, dict):
                errors.append(f"runtime[{event!r}][{i}] must be an object")
                continue
            if "api" not in item:
                errors.append(f"runtime[{event!r}][{i}] missing required 'api' field")
                continue
            if "args" not in item:
                errors.append(f"runtime[{event!r}][{i}] missing required 'args' field")
                continue
            if item["api"] not in _RUNTIME_API_ENUM:
                errors.append(f"runtime[{event!r}][{i}]: unknown runtime api {item['api']!r}")
            if not isinstance(item["args"], dict):
                errors.append(f"runtime[{event!r}][{i}].args must be an object")
            extra_keys = set(item.keys()) - {"api", "args"}
            if extra_keys:
                errors.append(f"runtime[{event!r}][{i}]: unexpected keys {sorted(extra_keys)}")
    return errors


_STORAGE_TYPE_ENUM = frozenset({"marker-file", "json-key", "json-array", "json-array-templated"})

_MUTATION_API_ENUM = frozenset({
    "write_marker",
    "delete_marker",
    "set_json_key",
    "delete_json_key",
    "append_json_array",
    "remove_json_array_value",
    "run_feature_script",
})

_COLOR_ENUM = frozenset({"red", "green", "yellow"})


def _validate_api_call(item, ctx):
    """Validate a single {api, args} mutation call. Returns list of errors."""
    errors = []
    if not isinstance(item, dict):
        errors.append(f"{ctx}: must be an object, got {type(item).__name__}")
        return errors
    if "api" not in item:
        errors.append(f"{ctx}: missing required 'api' field")
        return errors
    if "args" not in item:
        errors.append(f"{ctx}: missing required 'args' field")
        return errors
    if item["api"] not in _MUTATION_API_ENUM:
        errors.append(f"{ctx}: unknown mutation api {item['api']!r}")
    if not isinstance(item["args"], dict):
        errors.append(f"{ctx}.args must be an object")
    extra = set(item.keys()) - {"api", "args"}
    if extra:
        errors.append(f"{ctx}: unexpected keys {sorted(extra)}")
    return errors


def _validate_configuration(configuration):
    """Validate a configuration declaration. Returns list of error message strings."""
    errors = []
    if not isinstance(configuration, list):
        errors.append(f"configuration must be an array, got {type(configuration).__name__}")
        return errors
    for i, entry in enumerate(configuration):
        ctx = f"configuration[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{ctx} must be an object")
            continue
        if "id" not in entry:
            errors.append(f"{ctx} missing required 'id'")
            continue
        if "subcommand" not in entry:
            errors.append(f"{ctx} missing required 'subcommand'")
            continue
        has_values = "values" in entry
        has_actions = "actions" in entry
        if has_values == has_actions:
            errors.append(f"{ctx} must declare exactly one of 'values' or 'actions' (oneOf)")
        if has_values:
            if not isinstance(entry["values"], dict):
                errors.append(f"{ctx}.values must be an object")
            else:
                for k, call in entry["values"].items():
                    errors.extend(_validate_api_call(call, f"{ctx}.values[{k!r}]"))
                # Cross-field check: if a default is declared for a values-style
                # entry, it must name one of the declared value keys. Otherwise
                # the default is unreachable.
                if "default" in entry and entry["default"] not in entry["values"]:
                    errors.append(
                        f"{ctx}: default {entry['default']!r} is not a key in values; "
                        f"got values keys {sorted(entry['values'].keys())}"
                    )
                # Same check for alert-on: if declared, it must name a values key.
                if "alert-on" in entry and entry["alert-on"] not in entry["values"]:
                    errors.append(
                        f"{ctx}: alert-on {entry['alert-on']!r} is not a key in values; "
                        f"got values keys {sorted(entry['values'].keys())}"
                    )
        if has_actions:
            if not isinstance(entry["actions"], dict):
                errors.append(f"{ctx}.actions must be an object")
            else:
                for k, call in entry["actions"].items():
                    errors.extend(_validate_api_call(call, f"{ctx}.actions[{k!r}]"))
        if "storage" in entry:
            storage = entry["storage"]
            if not isinstance(storage, dict):
                errors.append(f"{ctx}.storage must be an object")
            elif "type" not in storage:
                errors.append(f"{ctx}.storage: missing required 'type' field")
            elif storage["type"] not in _STORAGE_TYPE_ENUM:
                errors.append(f"{ctx}.storage: unknown storage type {storage['type']!r}")
        if "alert-message" in entry:
            am = entry["alert-message"]
            if not isinstance(am, dict):
                errors.append(f"{ctx}.alert-message must be an object")
            else:
                for k in ("text", "icon", "color"):
                    if k not in am:
                        errors.append(f"{ctx}.alert-message missing required '{k}'")
                if "color" in am and am["color"] not in _COLOR_ENUM:
                    errors.append(f"{ctx}.alert-message.color must be one of {sorted(_COLOR_ENUM)}, got {am['color']!r}")
    return errors


def validate_meta_contract(feature_dir):
    """Validate a feature's meta-contract sections (manifest/runtime/configuration).

    Each section is optional. Returns a CheckResult; passed=True iff every
    declared section validates against its schema rules.
    """
    feature_json_path = os.path.join(feature_dir, "feature.json")
    if not os.path.isfile(feature_json_path):
        return CheckResult(passed=False, messages=[f"feature.json missing at {feature_json_path}"])
    try:
        with open(feature_json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return CheckResult(passed=False, messages=[f"feature.json invalid JSON: {e}"])
    if not isinstance(data, dict):
        return CheckResult(passed=False, messages=[f"feature.json must be a JSON object, got {type(data).__name__}"])

    errors = []
    if "manifest" in data:
        errors.extend(_validate_manifest(data["manifest"]))
    if "runtime" in data:
        errors.extend(_validate_runtime(data["runtime"]))
    if "configuration" in data:
        errors.extend(_validate_configuration(data["configuration"]))

    if errors:
        return CheckResult(passed=False, messages=errors)
    return CheckResult(passed=True, messages=["meta-contract sections valid (or absent)"])
