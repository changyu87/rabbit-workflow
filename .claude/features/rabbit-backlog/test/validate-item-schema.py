import json, sys
path = sys.argv[1]
try:
    d = json.load(open(path))
except Exception as e:
    print(f"invalid json: {e}")
    sys.exit(0)
issues = []
for field in ("name", "title", "status", "priority", "history"):
    if field not in d:
        issues.append(f"missing: {field}")
if d.get("status") != "open":
    issues.append(f"status != open (got: {d.get('status')!r})")
h = d.get("history", [])
first_action = h[0].get("action") if h else None
if first_action != "opened":
    issues.append(f"history[0].action != opened (got: {first_action!r})")
if issues:
    print("; ".join(issues))
