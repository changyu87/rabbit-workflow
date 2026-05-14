#!/bin/bash
# rabbit-project.sh — scaffold and maintain project directories.
#
# Usage:
#   rabbit-project.sh init <name>
#   rabbit-project.sh set-path <name> <absolute-path>
#   rabbit-project.sh map <name> <source-path> <feature-name>
#   rabbit-project.sh consolidate <name>
#
# Exit: 0 success, 1 error, 2 bad invocation

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
CONTRACT_TEMPLATES="$REPO_ROOT/.claude/features/contract/templates"

usage() {
  cat >&2 <<EOF
usage:
  rabbit-project.sh init <name>
  rabbit-project.sh set-path <name> <absolute-path>
  rabbit-project.sh map <name> <source-path> <feature-name>
  rabbit-project.sh consolidate <name>
EOF
}

cmd="${1:-}"; shift || true

case "$cmd" in
  init)
    name="${1:-}"
    [ -z "$name" ] && { usage; exit 2; }
    project_dir="$REPO_ROOT/project-$name"
    if [ -d "$project_dir" ]; then
      echo "ERROR: project-$name already exists at $project_dir" >&2
      exit 1
    fi
    mkdir -p "$project_dir/features" "$project_dir/contract"
    # Create project-map.json from template
    map_template="$CONTRACT_TEMPLATES/project-map-template.json"
    if [ ! -f "$map_template" ]; then
      echo "ERROR: template not found: $map_template" >&2
      exit 1
    fi
    sed -e "s/{{project_name}}/$name/g" \
        -e "s|{{absolute_source_root}}||g" \
        "$map_template" > "$project_dir/project-map.json"
    # Create features/registry.json from template
    reg_template="$CONTRACT_TEMPLATES/registry-template.json"
    if [ ! -f "$reg_template" ]; then
      echo "ERROR: template not found: $reg_template" >&2
      exit 1
    fi
    sed -e "s/{{owner}}/$name team/g" \
        "$reg_template" > "$project_dir/features/registry.json"
    echo "initialized project-$name/"
    ;;

  set-path)
    name="${1:-}"; path="${2:-}"
    [ -z "$name" ] || [ -z "$path" ] && { usage; exit 2; }
    project_map="$REPO_ROOT/project-$name/project-map.json"
    if [ ! -f "$project_map" ]; then
      echo "ERROR: project-map.json not found: $project_map" >&2
      exit 1
    fi
    if [ "${path#/}" = "$path" ]; then
      echo "ERROR: path must be absolute (start with /): $path" >&2
      exit 1
    fi
    python3 "$SCRIPT_DIR/rabbit-project-set-path.py" "$project_map" "$path"
    echo "set project-$name path to $path"
    ;;

  map)
    name="${1:-}"; source_path="${2:-}"; feature_name="${3:-}"
    [ -z "$name" ] || [ -z "$source_path" ] || [ -z "$feature_name" ] && { usage; exit 2; }
    project_map="$REPO_ROOT/project-$name/project-map.json"
    if [ ! -f "$project_map" ]; then
      echo "ERROR: project-map.json not found: $project_map" >&2
      exit 1
    fi
    python3 "$SCRIPT_DIR/rabbit-project-map.py" "$project_map" "$source_path" "$feature_name"
    echo "mapped $source_path -> $feature_name in project-$name"
    ;;

  consolidate)
    name="${1:-}"
    [ -z "$name" ] && { usage; exit 2; }
    project_map="$REPO_ROOT/project-$name/project-map.json"
    if [ ! -f "$project_map" ]; then
      echo "ERROR: project-map.json not found: $project_map" >&2
      exit 1
    fi
    registry="$REPO_ROOT/project-$name/features/registry.json"
    python3 "$SCRIPT_DIR/rabbit-project-consolidate.py" "$project_map" "$registry" "$name"
    echo "consolidated project-$name/project-map.json"
    ;;

  ""|-h|--help|help)
    usage; [ -z "$cmd" ] && exit 2 || exit 0
    ;;
  *)
    echo "ERROR: unknown subcommand '$cmd'" >&2
    usage; exit 2
    ;;
esac
