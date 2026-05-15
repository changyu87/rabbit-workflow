# rabbit-feature-scope — Contract

## Inputs
- `$1`: request description string (required)

## Outputs
- stdout: assembled prompt for default-model Agent dispatch
- stderr: status/error messages only
- exit 0: success; exit 2: invocation error

## Agent Response Schema

```json
{"features": ["feature-name-1"], "rationale": "one sentence"}
```

Rules:
- `features` contains only names present in `find-feature.py list`
- `rationale` is one sentence max
- Empty `features` list is valid
