"""
Shared pytest helpers for the rabbit-file test suite.

Currently empty: the previous `seed_bug_backlog_branch` helper was a
workaround for the BUG-32 chained-workspace local-origin guard, which was
removed in BACKLOG-12 along with the chained-workspace topology support.
Fixtures now rely on `_ensure_branch`'s bootstrap-on-first-use behaviour.
"""
