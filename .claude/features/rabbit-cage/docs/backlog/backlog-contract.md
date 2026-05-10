---
feature: rabbit-cage
version: 1.0.0
template_version: 2.0.0
---

# rabbit-cage — Backlog Item Contract

This contract defines the schema and lifecycle for backlog items managed under the rabbit-cage feature.

## Schema

```json
{
  "name": "string (ITEM-ID format, e.g. BACKLOG-001)",
  "title": "string",
  "status": "enum: open | in-progress | done | cancelled",
  "priority": "enum: low | medium | high | critical",
  "description": "string",
  "owner": "string",
  "filed": "ISO8601 datetime",
  "filed_by": "string",
  "closed": "ISO8601 datetime or null",
  "history": "array of {ts: ISO8601, actor: string, action: string, note: string}"
}
```

## Valid Status Values

- `open` — item has been filed and is awaiting work
- `in-progress` — work is actively underway
- `done` — work has been completed
- `cancelled` — item was abandoned or superseded

## Lifecycle — Valid Status Transitions

```
open → in-progress → done
open → cancelled
in-progress → cancelled
```

Invalid transitions (e.g. `done → open`, `cancelled → in-progress`) are rejected by `backlog-item-status.sh`.

## Deprecation Criterion

This contract is deprecated when rabbit-cage adopts a native backlog tracking system.
