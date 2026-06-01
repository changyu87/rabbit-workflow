---
feature: rabbit-issue
version: 1.1.0
owner: cyxu
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
      "rabbit-managed",
      "feature:<name>",
      "priority:<low|medium|high|critical>"
    ]
  },
  "reads": {
    "feature.json": "via rabbit-feature-scope (for --feature validation)",
    "github_issues": "via gh CLI; target repo slug resolves to RABBIT_ISSUE_REPO env var when set, else const `changyu87/rabbit-workflow` declared in _gh.py — never derived from cwd's git remote",
    "external": ["env-var:RABBIT_ISSUE_REPO"]
  },
  "invokes": {
    "rabbit-feature-scope": "skill — resolve feature for ambiguous filings",
    "gh": "CLI tool — issue create/view/close/reopen/list, label create"
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "writes to origin/bug-backlog-files (deleted by migration)",
    "maintains counter.json (GH allocates issue numbers)",
    "maintains item.json history array (GH Timeline is source of truth)",
    "closes/reopens issues lacking the `rabbit-managed` label"
  ]
}
```
