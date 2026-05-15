#!/usr/bin/env python3
# test-workspace-map.py — verify rabbit-workspace-map skill invariants (spec invariants 6, 7, 8).
#
# Checks:
#   (a) workspace-map.py exists and is executable
#   (b) workspace-map.json.schema.json exists and is valid JSON
#   (c) workspace-map.json.schema.json declares schemaVersion and required properties
#   (d) workspace-map.py produces valid JSON without flags
#   (e) workspace-map.py --human produces non-JSON human-readable output
#   (f) .claude/features/contract/skills/rabbit-workspace-map/SKILL.md exists (source of truth)
#   (g) feature.json surface.skills contains 'rabbit-workspace-map'
#   (h) SKILL.md references workspace-map.py and the --human flag
#   (i) SKILL.md instructs Claude to directly execute workspace-map.py on invocation
#   (j) Deployed copy at .claude/skills/rabbit-workspace-map/SKILL.md is in sync with source
#   ... and more

import os
import sys
import json
import subprocess
import tempfile
import shutil
import re
import filecmp

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

SCRIPT = os.path.join(FEATURE_DIR, "scripts/workspace-map.py")
SCHEMA = os.path.join(FEATURE_DIR, "schemas/workspace-map.json.schema.json")
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-workspace-map/SKILL.md")
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
FAIL = 0


def fail_check(label, msg):
    global FAIL
    print(f"FAIL ({label}): {msg}", file=sys.stderr)
    FAIL = 1


def ok_check(label, msg):
    print(f"ok ({label}): {msg}")


# (a) workspace-map.py exists and is executable
if not os.path.isfile(SCRIPT):
    fail_check("a", f"workspace-map.py missing: {SCRIPT}")
elif not os.access(SCRIPT, os.X_OK):
    fail_check("a", f"workspace-map.py not executable: {SCRIPT}")
else:
    ok_check("a", "workspace-map.py exists and is executable")

# (b) workspace-map.json.schema.json exists and is valid JSON
schema_data = None
if not os.path.isfile(SCHEMA):
    fail_check("b", f"workspace-map.json.schema.json missing: {SCHEMA}")
else:
    try:
        schema_data = json.load(open(SCHEMA))
        ok_check("b", "workspace-map.json.schema.json exists and is valid JSON")
    except (json.JSONDecodeError, OSError):
        fail_check("b", "workspace-map.json.schema.json is not valid JSON")

# (c) output schema schemaVersion is 2.0.0 (top-level field)
if schema_data is not None:
    sv = schema_data.get("schemaVersion", "")
    if sv == "2.0.0":
        ok_check("c", "workspace-map.json.schema.json schemaVersion is 2.0.0")
    else:
        fail_check("c", f"workspace-map.json.schema.json schemaVersion is '{sv}' (expected 2.0.0)")

# (d) workspace-map.py produces valid JSON with v2 shape
if os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK):
    r = subprocess.run(["python3", SCRIPT], capture_output=True, text=True)
    JSON_OUT = r.stdout
    if not JSON_OUT.strip():
        fail_check("d", "workspace-map.py produced no output")
    else:
        try:
            d_data = json.loads(JSON_OUT)
            ok_check("d1", "workspace-map.py produces valid JSON")
            d_ver = d_data.get("schemaVersion", "")
            if d_ver == "2.0.0":
                ok_check("d2", "output schemaVersion is 2.0.0")
            else:
                fail_check("d2", f"output schemaVersion is '{d_ver}' (expected 2.0.0)")
            if "roots" in d_data:
                ok_check("d3", "output has 'roots' key")
            else:
                fail_check("d3", "output missing 'roots' key")
        except json.JSONDecodeError:
            fail_check("d", "workspace-map.py output is not valid JSON")

# (e) workspace-map.py --human produces non-JSON human-readable output
if os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK):
    r = subprocess.run(["python3", SCRIPT, "--human"], capture_output=True, text=True)
    HUMAN_OUT = r.stdout
    if not HUMAN_OUT.strip():
        fail_check("e", "workspace-map.py --human produced no output")
    else:
        try:
            json.loads(HUMAN_OUT)
            fail_check("e", "workspace-map.py --human output is JSON (expected human-readable text)")
        except json.JSONDecodeError:
            ok_check("e", "workspace-map.py --human produces non-JSON output")

# (f) Source SKILL.md exists under contract feature
if not os.path.isfile(SKILL_MD):
    fail_check("f", f"source SKILL.md missing: {SKILL_MD}")
else:
    ok_check("f", "rabbit-workspace-map/SKILL.md exists at source location")

# (g) feature.json surface.skills is []
if not os.path.isfile(FEATURE_JSON):
    fail_check("g", f"feature.json missing: {FEATURE_JSON}")
else:
    try:
        fj = json.load(open(FEATURE_JSON))
        skills = fj.get("surface", {}).get("skills", [])
        if skills == []:
            ok_check("g", "feature.json surface.skills is [] (retired)")
        else:
            fail_check("g", f"feature.json surface.skills is not [] (was: {json.dumps(skills)})")
    except (json.JSONDecodeError, OSError) as e:
        fail_check("g", f"could not parse feature.json: {e}")

# (h) SKILL.md references workspace-map.py and the --human flag
if os.path.isfile(SKILL_MD):
    skill_content = open(SKILL_MD).read()
    if "workspace-map.py" not in skill_content:
        fail_check("h", "SKILL.md does not reference workspace-map.py")
    else:
        ok_check("h1", "SKILL.md references workspace-map.py")
    if "--human" not in skill_content:
        fail_check("h", "SKILL.md does not reference --human flag")
    else:
        ok_check("h2", "SKILL.md references --human flag")
    if "--audit" not in skill_content:
        fail_check("h3", "SKILL.md does not reference --audit flag")
    else:
        ok_check("h3", "SKILL.md references --audit flag")

# (i) SKILL.md instructs Claude to execute workspace-map.py on invocation
if os.path.isfile(SKILL_MD):
    skill_content = open(SKILL_MD).read()
    if not re.search(r'(?im)^\s*(execute|run|invoke|immediately\s+(execute|run|invoke))\b', skill_content):
        fail_check("i", "SKILL.md lacks an imperative execution directive (e.g., 'Execute', 'Run', 'Invoke') as a top-level instruction")
    else:
        ok_check("i1", "SKILL.md uses imperative execution language")

    if not re.search(r'(use|pass|with|add)\s+`?--human`?', skill_content):
        fail_check("i", "SKILL.md does not present --human as an action to take")
    else:
        ok_check("i2", "SKILL.md presents --human as an action")

    if not re.search(r'(?i)(default\s+json|json\s+(mode|output|by\s+default)|without\s+`?--human`?|omit\s+`?--human`?)', skill_content):
        fail_check("i", "SKILL.md does not present default JSON as the programmatic mode")
    else:
        ok_check("i3", "SKILL.md presents default JSON as programmatic mode")

# (j) Deployed copy at .claude/skills/rabbit-workspace-map/SKILL.md is in sync with source
DEPLOYED_SKILL_MD = os.path.join(REPO_ROOT, ".claude/skills/rabbit-workspace-map/SKILL.md") if REPO_ROOT else ""
if not REPO_ROOT:
    fail_check("j", "cannot resolve repo root for deployed-copy check")
elif not os.path.isfile(DEPLOYED_SKILL_MD):
    fail_check("j", f"deployed SKILL.md missing: {DEPLOYED_SKILL_MD}")
elif not filecmp.cmp(SKILL_MD, DEPLOYED_SKILL_MD, shallow=False):
    fail_check("j", "deployed SKILL.md differs from source — run cp -rp to sync")
else:
    ok_check("j", "deployed SKILL.md matches source")

# (k) workspace-structure.json schema exists and is valid JSON
WS_SCHEMA = os.path.join(FEATURE_DIR, "schemas/workspace-structure.json")
ws_schema_data = None
if not os.path.isfile(WS_SCHEMA):
    fail_check("k", f"workspace-structure.json schema missing: {WS_SCHEMA}")
else:
    try:
        ws_schema_data = json.load(open(WS_SCHEMA))
        ok_check("k", "workspace-structure.json schema exists and is valid JSON")
    except (json.JSONDecodeError, OSError):
        fail_check("k", "workspace-structure.json schema is not valid JSON")

# (l) workspace-structure.json schema has required top-level properties
if ws_schema_data is not None:
    props = ws_schema_data.get("properties", {})
    for field in ["schema_version", "owner", "root", "nodes"]:
        if field in props:
            ok_check("l", f"schema has property: {field}")
        else:
            fail_check("l", f"workspace-structure.json schema missing property: {field}")

# (m) .claude/workspace-structure.json exists and is valid JSON
RABBIT_DECL = os.path.join(REPO_ROOT, ".claude/workspace-structure.json") if REPO_ROOT else ""
rabbit_decl_data = None
if not RABBIT_DECL:
    fail_check("m", "no repo root for .claude/workspace-structure.json check")
elif not os.path.isfile(RABBIT_DECL):
    fail_check("m", f".claude/workspace-structure.json missing: {RABBIT_DECL}")
else:
    try:
        rabbit_decl_data = json.load(open(RABBIT_DECL))
        ok_check("m", ".claude/workspace-structure.json exists and is valid JSON")
    except (json.JSONDecodeError, OSError):
        fail_check("m", ".claude/workspace-structure.json is not valid JSON")

# (n) rabbit declaration has root "rabbit" and required top-level nodes
if rabbit_decl_data is not None:
    rabbit_root_tag = rabbit_decl_data.get("root", "")
    if rabbit_root_tag == "rabbit":
        ok_check("n", "declaration root is 'rabbit'")
    else:
        fail_check("n", f".claude/workspace-structure.json root is not 'rabbit' (got: {rabbit_root_tag})")

    node_names = [n["name"] for n in rabbit_decl_data.get("nodes", [])]
    for req_node in ["features", "skills", "hooks", "commands"]:
        if req_node in node_names:
            ok_check("n", f"rabbit declaration declares node: {req_node}")
        else:
            fail_check("n", f"rabbit declaration missing required node: {req_node}")

# (o) output schema declares schemaVersion 2.0.0 at top level
if schema_data is not None:
    o_ver = schema_data.get("schemaVersion", "")
    if o_ver == "2.0.0":
        ok_check("o", "output schema schemaVersion is 2.0.0")
    else:
        fail_check("o", f"output schema schemaVersion is '{o_ver}' (expected 2.0.0)")

# (p) output schema has 'roots' property and not stale 'features' flat array
if schema_data is not None:
    def has_roots(obj):
        if "roots" in obj.get("properties", {}):
            return True
        for branch in obj.get("oneOf", []):
            if "roots" in branch.get("properties", {}):
                return True
        return False

    if has_roots(schema_data):
        ok_check("p1", "output schema has 'roots' property")
    else:
        fail_check("p1", "output schema missing 'roots' property")

    if "features" not in schema_data.get("properties", {}):
        ok_check("p2", "output schema does not have stale 'features' flat array")
    else:
        fail_check("p2", "output schema still has old 'features' flat array (must be removed in v2)")

# (q) output schema has 'findings' property (audit mode)
if schema_data is not None:
    def has_findings(obj):
        if "findings" in obj.get("properties", {}):
            return True
        for branch in obj.get("oneOf", []):
            if "findings" in branch.get("properties", {}):
                return True
        return False

    if has_findings(schema_data):
        ok_check("q", "output schema has 'findings' property (audit mode)")
    else:
        fail_check("q", "output schema missing 'findings' property")

# Behavioral tests using --repo-root with a controlled temp directory.
BT_TMP = tempfile.mkdtemp()
try:
    subprocess.run(["git", "-C", BT_TMP, "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", BT_TMP, "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", BT_TMP, "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", BT_TMP, "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)

    os.makedirs(os.path.join(BT_TMP, ".claude/declared_req"), exist_ok=True)
    os.makedirs(os.path.join(BT_TMP, ".claude/extra_unknown"), exist_ok=True)

    decl = {
        "schema_version": "1.0.0",
        "owner": "test",
        "root": "rabbit",
        "nodes": [
            {"name": "declared_req", "required": True, "description": "required dir, present", "children": []},
            {"name": "declared_opt", "required": False, "description": "optional dir, absent", "children": []},
            {"name": "declared_req_missing", "required": True, "description": "required dir, absent", "children": []}
        ]
    }
    with open(os.path.join(BT_TMP, ".claude/workspace-structure.json"), "w") as f:
        json.dump(decl, f, indent=2)

    if os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK):
        # (r) show mode JSON
        r = subprocess.run(
            ["python3", SCRIPT, "--repo-root", BT_TMP],
            capture_output=True, text=True
        )
        try:
            bt_out = json.loads(r.stdout)
            bt_ver = bt_out.get("schemaVersion", "")
            if bt_ver == "2.0.0":
                ok_check("r1", "show mode schemaVersion is 2.0.0")
            else:
                fail_check("r1", f"show mode schemaVersion is '{bt_ver}' (expected 2.0.0)")

            nodes = bt_out["roots"][0]["nodes"]

            n_req = next((x for x in nodes if x["name"] == "declared_req"), None)
            req_status = n_req["status"] if n_req else "NOT_FOUND"
            if req_status == "present":
                ok_check("r2", "declared_req status is 'present'")
            else:
                fail_check("r2", f"declared_req status is '{req_status}' (expected 'present')")

            n_opt = next((x for x in nodes if x["name"] == "declared_opt"), None)
            opt_status = n_opt["status"] if n_opt else "NOT_FOUND"
            if opt_status == "missing":
                ok_check("r3", "declared_opt status is 'missing'")
            else:
                fail_check("r3", f"declared_opt status is '{opt_status}' (expected 'missing')")

            n_unk = next((x for x in nodes if x["name"] == "extra_unknown"), None)
            unk_str = f"{n_unk['status'] if n_unk else 'NOT_FOUND'},{str(n_unk['required']) if n_unk else 'X'}"
            if unk_str == "unknown,None":
                ok_check("r4", "extra_unknown status is 'unknown' with required null")
            else:
                fail_check("r4", f"extra_unknown is '{unk_str}' (expected 'unknown,None')")
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            fail_check("r", f"show mode output parsing failed: {e}")

        # (s) audit mode
        r_audit = subprocess.run(
            ["python3", SCRIPT, "--repo-root", BT_TMP, "--audit"],
            capture_output=True, text=True
        )
        try:
            bt_audit = json.loads(r_audit.stdout)

            if "findings" in bt_audit:
                ok_check("s1", "audit output has findings array")
            else:
                fail_check("s1", "audit output missing findings array")

            f_s2 = next((x for x in bt_audit.get("findings", []) if x["type"] == "missing_required" and "declared_req_missing" in x["path"]), None)
            s2_sev = f_s2["severity"] if f_s2 else "NOT_FOUND"
            if s2_sev == "error":
                ok_check("s2", "missing required node emits severity 'error'")
            else:
                fail_check("s2", f"missing_required finding not found or wrong severity (got: '{s2_sev}')")

            f_s3 = next((x for x in bt_audit.get("findings", []) if x["type"] == "unknown" and "extra_unknown" in x["path"]), None)
            s3_sev = f_s3["severity"] if f_s3 else "NOT_FOUND"
            if s3_sev == "warn":
                ok_check("s3", "unknown node emits severity 'warn'")
            else:
                fail_check("s3", f"unknown finding not found or wrong severity (got: '{s3_sev}')")

            f_s4 = next((x for x in bt_audit.get("findings", []) if "declared_opt" in x["path"]), None)
            if f_s4 is None:
                ok_check("s4", "missing optional node emits no audit finding")
            else:
                fail_check("s4", "missing optional node unexpectedly emitted a finding")
        except (json.JSONDecodeError, KeyError) as e:
            fail_check("s", f"audit output parsing failed: {e}")

        # (t) user project without declaration → declaration "missing"
        os.makedirs(os.path.join(BT_TMP, "my-project"), exist_ok=True)
        r2 = subprocess.run(
            ["python3", SCRIPT, "--repo-root", BT_TMP],
            capture_output=True, text=True
        )
        try:
            bt_out2 = json.loads(r2.stdout)
            proj = next((r for r in bt_out2["roots"] if r["root"] == "my-project"), None)
            proj_decl = proj["declaration"] if proj else "NOT_FOUND"
            if proj_decl == "missing":
                ok_check("t", "user project without declaration has declaration 'missing'")
            else:
                fail_check("t", f"user project declaration status is '{proj_decl}' (expected 'missing')")
        except (json.JSONDecodeError, KeyError) as e:
            fail_check("t", f"output parsing failed: {e}")

        # (u) audit emits missing_declaration warn for user project without workspace-structure.json
        r_audit2 = subprocess.run(
            ["python3", SCRIPT, "--repo-root", BT_TMP, "--audit"],
            capture_output=True, text=True
        )
        try:
            bt_audit2 = json.loads(r_audit2.stdout)
            f_u = next((x for x in bt_audit2.get("findings", []) if x["type"] == "missing_declaration" and "my-project" in x["path"]), None)
            u_sev = f_u["severity"] if f_u else "NOT_FOUND"
            if u_sev == "warn":
                ok_check("u", "missing user project declaration emits 'warn' finding")
            else:
                fail_check("u", f"missing_declaration finding not found or wrong severity (got: '{u_sev}')")
        except (json.JSONDecodeError, KeyError) as e:
            fail_check("u", f"audit2 output parsing failed: {e}")

    # (v) workspace-map.py --audit produces valid JSON with findings key
    if os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK):
        r_v = subprocess.run(["python3", SCRIPT, "--audit"], capture_output=True, text=True)
        AUDIT_OUT = r_v.stdout
        if not AUDIT_OUT.strip():
            fail_check("v", "workspace-map.py --audit produced no output")
        else:
            try:
                audit_data = json.loads(AUDIT_OUT)
                ok_check("v1", "workspace-map.py --audit produces valid JSON")
                if "findings" in audit_data:
                    ok_check("v2", "audit output has 'findings' key")
                else:
                    fail_check("v2", "audit output missing 'findings' key")
            except json.JSONDecodeError:
                fail_check("v", "workspace-map.py --audit output is not valid JSON")

    # (w) workspace-map.py --audit --human produces non-JSON human-readable output
    if os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK):
        r_w = subprocess.run(["python3", SCRIPT, "--audit", "--human"], capture_output=True, text=True)
        AUDIT_H_OUT = r_w.stdout
        if not AUDIT_H_OUT.strip():
            fail_check("w", "workspace-map.py --audit --human produced no output")
        else:
            try:
                json.loads(AUDIT_H_OUT)
                fail_check("w", "workspace-map.py --audit --human output is JSON (expected human-readable text)")
            except json.JSONDecodeError:
                ok_check("w", "workspace-map.py --audit --human produces non-JSON output")

finally:
    shutil.rmtree(BT_TMP, ignore_errors=True)

# (x) spec.md prose checks — invariant 6 and 7 wording
SPEC_MD = os.path.join(FEATURE_DIR, "docs/spec/spec.md")
if os.path.isfile(SPEC_MD):
    spec_content = open(SPEC_MD).read()
    if "conforms to its own" in spec_content:
        fail_check("x1", "spec.md still contains stale self-conformance wording in invariant 7")
    else:
        ok_check("x1", "spec.md invariant 7 does not claim self-conformance")

    if "keyed on" in spec_content:
        fail_check("x2", "spec.md still contains 'keyed on' wording in invariant 7")
    else:
        ok_check("x2", "spec.md invariant 7 does not use 'keyed on'")

    if "missing_declaration" in spec_content:
        ok_check("x3", "spec.md invariant 6 mentions missing_declaration")
    else:
        fail_check("x3", "spec.md invariant 6 missing 'missing_declaration' finding type")

if FAIL != 0:
    print("test-workspace-map: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-workspace-map: all checks passed.")
