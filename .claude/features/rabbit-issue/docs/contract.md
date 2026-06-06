---
feature: rabbit-issue
version: 1.12.0
owner: rabbit-workflow team
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker; revisit when claude-plugins-official ships a GH Issues skill
---

# rabbit-issue — Contract

```json
{
  "provides": {
    "skill": "rabbit-issue",
    "scripts": [
      "scripts/file-item.py",
      "scripts/item-status.py",
      "scripts/list-items.py",
      "scripts/_gh.py"
    ],
    "issue_labels": [
      "bug",
      "enhancement",
      "feature:<name>",
      "priority:<low|medium|high|critical>",
      "filed-by:<rabbit|autonomous-evolve>",
      "housekeeping",
      "in-progress"
    ]
  },
  "reads": {
    "feature.json": "via rabbit-feature-scope (for --feature validation)",
    "github_issues": "via gh CLI; target repo slug resolves to RABBIT_ISSUE_REPO env var when set, else const `changyu87/rabbit-workflow` declared in _gh.py — never derived from cwd's git remote",
    "external": ["env-var:RABBIT_ISSUE_REPO"]
  },
  "invokes": {
    "rabbit-feature-scope": "skill — resolve feature for ambiguous filings",
    "gh": "CLI tool — issue create/view/close/reopen/list, label create; issue comments are read via `gh issue view <N> --json comments` (NOT --comments, which hits deprecated projectCards GraphQL and returns empty); sub-issue linkage uses `gh api repos/{slug}/issues/{child}` to resolve the child database id and POSTs `gh api repos/{slug}/issues/{parent}/sub_issues` with `{\"sub_issue_id\": <child_id>}`"
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "writes to origin/bug-backlog-files (not a rabbit-issue surface)",
    "maintains counter.json (GH allocates issue numbers)",
    "maintains item.json history array (GH Timeline is source of truth)",
    "closes/reopens non-actionable issues (those lacking a valid `feature:` label)",
    "stamps a `filed-by:` label outside the fixed enum {rabbit, autonomous-evolve}",
    "reads issue comments via `gh issue view --comments` (deprecated projectCards GraphQL path)"
  ]
}
```
