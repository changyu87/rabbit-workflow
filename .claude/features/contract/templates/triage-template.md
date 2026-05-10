<!-- template_version: 1.0.0 -->

## TRIAGE output format

Produce exactly this block. No prose outside it.

```
TRIAGE:
  bug_name:           <name>
  current_status:     <open|closed|reopened>
  related_feature:    <name | null>
  classification:     <new | known | invalid | test-gap>
  severity_assessed:  <low | medium | high | critical>
  evidence:           |
                      <multi-line: what you read, what you found,
                       what supports your classification>
  recommended_action: <one of: keep_open | close_invalid | close_duplicate |
                              route_to_feature_owner | escalate>
  recommended_test:   <test name to add — only when classification is test-gap, else null>
  proposed_handoff:   <e.g. "dispatch feature owner to add test X" or
                       "no handoff: caller closes bug">
```

## Classifications

| Classification | Meaning |
|---|---|
| `new` | Genuine unique bug; needs a fix. |
| `known` | Duplicate of an existing open bug. |
| `invalid` | Not a bug; misunderstanding or by design. |
| `test-gap` | Reveals missing test coverage; needs test work. |

A bug can be `new` AND `test-gap` simultaneously — state both.
