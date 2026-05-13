#!/usr/bin/env bash
# workspace-map.sh — contract-driven workspace hierarchy map.
#
# Usage (show mode, default):
#   workspace-map.sh [--human] [--repo-root <path>]
#   Produces JSON conforming to workspace-map.json.schema.json v2.0.0.
#
# Usage (audit mode):
#   workspace-map.sh --audit [--human] [--repo-root <path>]
#   Produces findings-only JSON (deviations from contract).
#
# Usage (backlog path, legacy subcommand — preserved for rabbit-backlog):
#   workspace-map.sh backlog <feature-name> [--repo-root <path>]
#   Outputs the canonical backlog directory path for the named feature.
#
# Exit:
#   0  success
#   1  error
#
# Owner: rabbit-workflow team (contract feature)
# Version: 2.0.0
# Deprecation criterion: when rabbit features adopt a native workspace registry.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_root() {
  local root_arg="$1"
  if [ -n "$root_arg" ]; then
    echo "$root_arg"
  elif [ -n "${RABBIT_ROOT:-}" ]; then
    echo "$RABBIT_ROOT"
  else
    git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null \
      || { echo "ERROR: cannot resolve repo root" >&2; exit 1; }
  fi
}

# ---------------------------------------------------------------------------
# Legacy subcommand: backlog (used by rabbit-backlog/file-backlog-item.sh)
# ---------------------------------------------------------------------------
if [ "${1:-}" = "backlog" ]; then
  shift
  FEATURE_NAME="${1:-}"
  shift || true
  REPO_ROOT_ARG=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) REPO_ROOT_ARG="$2"; shift 2 ;;
      *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
    esac
  done
  if [ -z "$FEATURE_NAME" ]; then
    echo "ERROR: feature-name is required" >&2
    exit 1
  fi
  RESOLVED_ROOT="$(resolve_root "$REPO_ROOT_ARG")"
  echo "${RESOLVED_ROOT}/.claude/backlogs/${FEATURE_NAME}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
HUMAN=0
AUDIT=0
REPO_ROOT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --human)     HUMAN=1; shift ;;
    --audit)     AUDIT=1; shift ;;
    --repo-root) REPO_ROOT_ARG="$2"; shift 2 ;;
    -h|--help)   echo "usage: workspace-map.sh [--human] [--audit] [--repo-root <path>]"; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(resolve_root "$REPO_ROOT_ARG")"

python3 << PYEOF
import json, os, sys

REPO_ROOT = "$REPO_ROOT"
HUMAN = $HUMAN
AUDIT = $AUDIT
CLAUDE_DIR = os.path.join(REPO_ROOT, ".claude")

def load_declaration(filepath):
    if not os.path.isfile(filepath):
        return None
    try:
        d = json.load(open(filepath))
        for req in ("schema_version", "owner", "root", "nodes"):
            if req not in d:
                return None
        return d
    except Exception:
        return None

def walk_nodes(declared_nodes, fs_path):
    declared_names = {n["name"] for n in declared_nodes}
    try:
        actual_dirs = {e for e in os.listdir(fs_path)
                       if os.path.isdir(os.path.join(fs_path, e))}
    except Exception:
        actual_dirs = set()
    result = []
    for node in declared_nodes:
        node_fs = os.path.join(fs_path, node["name"])
        status = "present" if os.path.isdir(node_fs) else "missing"
        children = walk_nodes(node.get("children", []), node_fs) if status == "present" else []
        result.append({
            "name": node["name"],
            "required": node["required"],
            "description": node.get("description", ""),
            "status": status,
            "children": children,
        })
    for name in sorted(actual_dirs - declared_names):
        if name.startswith("."):
            continue
        result.append({
            "name": name,
            "required": None,
            "description": "",
            "status": "unknown",
            "children": [],
        })
    return result

def collect_findings(nodes, path_prefix, root_name):
    findings = []
    for node in nodes:
        full = os.path.join(path_prefix, node["name"])
        if node["status"] == "missing" and node["required"] is True:
            findings.append({"severity": "error", "type": "missing_required", "path": full, "root": root_name})
        elif node["status"] == "unknown":
            findings.append({"severity": "warn", "type": "unknown", "path": full, "root": root_name})
        if node.get("children"):
            findings.extend(collect_findings(node["children"], full, root_name))
    return findings

def print_nodes_human(nodes, indent):
    for node in nodes:
        req_label = "[required]" if node["required"] is True else ("[optional]" if node["required"] is False else "[UNKNOWN] ")
        status_label = node["status"].upper()
        print("{}  {}/  {}  {}".format("  " * indent, node["name"], req_label, status_label))
        if node.get("children"):
            print_nodes_human(node["children"], indent + 1)

# Rabbit root
rabbit_decl = load_declaration(os.path.join(CLAUDE_DIR, "workspace-structure.json"))
rabbit_nodes = walk_nodes(rabbit_decl["nodes"], CLAUDE_DIR) if rabbit_decl else []
rabbit_root = {
    "root": rabbit_decl["root"] if rabbit_decl else "rabbit",
    "path": ".claude",
    "declaration": "found" if rabbit_decl else "missing",
    "nodes": rabbit_nodes,
}

# User project roots
user_roots = []
try:
    entries = sorted(
        e for e in os.listdir(REPO_ROOT)
        if not e.startswith(".") and os.path.isdir(os.path.join(REPO_ROOT, e))
    )
except Exception:
    entries = []

for entry in entries:
    proj_path = os.path.join(REPO_ROOT, entry)
    proj_decl = load_declaration(os.path.join(proj_path, "workspace-structure.json"))
    if proj_decl:
        nodes = walk_nodes(proj_decl["nodes"], proj_path)
        user_roots.append({"root": proj_decl["root"], "path": entry, "declaration": "found", "nodes": nodes})
    else:
        user_roots.append({"root": entry, "path": entry, "declaration": "missing", "nodes": []})

all_roots = [rabbit_root] + user_roots

# Audit findings
all_findings = []
if AUDIT:
    if rabbit_decl is None:
        all_findings.append({"severity": "warn", "type": "missing_declaration", "path": ".claude", "root": "rabbit"})
    else:
        all_findings.extend(collect_findings(rabbit_nodes, ".claude", rabbit_root["root"]))
    for r in user_roots:
        if r["declaration"] == "missing":
            all_findings.append({"severity": "warn", "type": "missing_declaration", "path": r["path"], "root": r["root"]})
        else:
            all_findings.extend(collect_findings(r["nodes"], r["path"], r["root"]))

# Output
if HUMAN:
    if AUDIT:
        print("=== rabbit workspace audit ===")
        if not all_findings:
            print("  no deviations found")
        for f in all_findings:
            sev = "ERROR" if f["severity"] == "error" else "WARN "
            print("  {}  {}  {}".format(sev, f["type"], f["path"]))
    else:
        print("=== rabbit workspace map ===")
        print("repo: {}".format(REPO_ROOT))
        print()
        for r in all_roots:
            print("--- {} [{}] ({}) ---".format(r["root"], r["declaration"], r["path"]))
            print_nodes_human(r["nodes"], 0)
            print()
else:
    if AUDIT:
        print(json.dumps({"schemaVersion": "2.0.0", "findings": all_findings}, indent=2))
    else:
        print(json.dumps({"schemaVersion": "2.0.0", "repoRoot": REPO_ROOT, "roots": all_roots}, indent=2))
PYEOF
