<!-- template_version: 2.0.0 -->

# Handoff Format

On completion of any dispatched task, emit exactly one HANDOFF block. No
prose outside the block. The dispatcher reads this block to determine next
action.

```
HANDOFF:
  feature:        <feature-name>
  task:           <the one-sentence task from TASK section>
  files_touched:  [<repo-relative path>, ...]
  verify_results: [<criterion>: pass|fail, ...]
  next_action:    <dispatcher_proceeds|needs_review|blocked:<reason>>
  tdd_gap:        <omit for non-bug dispatches — include TDD_GAP block below for bug fixes>
```

For bug-fix dispatches, append inside the HANDOFF block:

```
TDD_GAP:
  bug_id:            <e.g. RABBIT-CAGE-9>
  existed:           yes | no | untestable
  test_path:         <relative path under feature-dir/test/ | null>
  test_name:         <test name | null>
  added_or_extended: added | extended | none
  verified_red:      yes | no | n/a
  verified_green:    yes | no | n/a
  would_have_caught: yes | no
  note:              <one sentence; required when existed=untestable or any no/n/a>
```

Fields:
- `existed: yes` — test existed but didn't exercise the failing path → extended
- `existed: no`  — no test existed → added
- `existed: untestable` — escape hatch, requires note; main session may reject
- `would_have_caught: no` contradicts a successful fix; main session will reject
