"""contract.lib.producers — content producers for publish_generated.

Each producer takes producer-specific named args (forwarded from a feature's
MANIFEST entry) plus keyword-only `feature_dir` and `repo_root` context, and
returns generated content as a string. The producer registry maps the
kebab-case producer names declared in MANIFESTs to these Python functions;
`call_producer(name, args, *, feature_dir, repo_root)` is the dispatcher
that lib.publish.publish_generated invokes.

Path-arg convention (applies to every producer's path args):
  - Absolute paths pass through unchanged.
  - Relative paths starting with ".claude/" resolve against repo_root.
  - All other relative paths resolve against feature_dir.

Future producers documented but not implemented here:
  - compose-template(template, args) — template substitution. Deferred per
    the meta-contract design doc until first concrete need.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native content producers.
"""

import os


def _resolve(path: str, feature_dir: str, repo_root: str) -> str:
    """Resolve a producer arg path per the module-level convention."""
    if os.path.isabs(path):
        return path
    if path.startswith(".claude/"):
        return os.path.join(repo_root, path)
    return os.path.join(feature_dir, path)


def read_file(path: str, *, feature_dir: str, repo_root: str) -> str:
    """Return the contents of `path` (resolved per the module-level
    convention) as a string. Raises FileNotFoundError if the file is
    missing — caller (typically publish_generated) propagates the error.
    """
    with open(_resolve(path, feature_dir, repo_root)) as f:
        return f.read()


# Registry: MANIFEST kebab-case producer names → Python functions.
# Populated by Tasks 2-4 (read-file, expand-at-imports, generate-claude-md).
PRODUCERS = {
    "read-file": read_file,
}


def call_producer(name: str, args: dict, *,
                  feature_dir: str, repo_root: str) -> str:
    """Dispatch `name` to its registered producer with `args` (forwarded as
    kwargs) plus the keyword-only context params. Returns the producer's
    generated content as a string. Raises KeyError if `name` is not in the
    registry — feature MANIFEST authors are responsible for using valid
    producer names.
    """
    if name not in PRODUCERS:
        raise KeyError(f"unknown producer: {name}")
    return PRODUCERS[name](feature_dir=feature_dir, repo_root=repo_root, **args)
