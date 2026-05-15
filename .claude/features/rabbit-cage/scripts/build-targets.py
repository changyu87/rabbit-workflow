#!/usr/bin/env python3
# build-targets.py — process build-contract.json targets
# Usage: python3 build-targets.py <repo_root> <contract_path> <generate_script>
import hashlib, json, os, re, shutil, subprocess, sys

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

repo_root, contract_path, generate_script = sys.argv[1], sys.argv[2], sys.argv[3]

with open(contract_path) as f:
    contract = json.load(f)

errors = 0
for target in contract.get("targets", []):
    name = target["name"]
    ttype = target["type"]
    destination = os.path.join(repo_root, target["destination"])

    if ttype == "generate-claude-md":
        env = dict(os.environ)
        env["RABBIT_ROOT"] = repo_root
        result = subprocess.run(
            [sys.executable, generate_script, "--write", repo_root],
            capture_output=True, text=True,
            env=env
        )
        if result.returncode != 0:
            print(f"  [error] {name}: generate-claude-md failed\n{result.stderr}", file=sys.stderr)
            errors += 1
        else:
            print(f"  [built] {name}")

    elif ttype == "copy-file":
        source = os.path.join(repo_root, target["source"])
        if not os.path.isfile(source):
            print(f"  [error] build: source not found: {target['source']}", file=sys.stderr)
            errors += 1
            continue
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        # Gate the copy and the .rabbit-skills-updated marker write on actual
        # content change: skip both when destination already has identical
        # sha256 to source. (Spec Invariant 24(a).)
        content_changed = (not os.path.isfile(destination)) or \
                          (_sha256(source) != _sha256(destination))
        if content_changed:
            shutil.copy2(source, destination)
        print(f"  [built] {name}")
        m = re.match(r'^\.claude/skills/([^/]+)/SKILL\.md$', target["destination"])
        if m and content_changed:
            marker = os.path.join(repo_root, ".rabbit-skills-updated")
            with open(marker, "a") as f:
                f.write(m.group(1) + "\n")

    else:
        print(f"  [error] unknown type '{ttype}' for target '{name}'", file=sys.stderr)
        errors += 1

if errors:
    print(f"\nbuild: {errors} error(s)", file=sys.stderr)
    sys.exit(1)
