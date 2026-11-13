# memory/

Working state for tasks, not ideas. `knowledge/` says what is durably true;
`memory/` says where a piece of work stands right now: what was tried, what
worked, what didn't, what's still open. It is how an agent session that
starts cold (or gets interrupted) picks up where the last one stopped.

One file per task, named for the thing it tracks (`nas-migration.md`, not
`2026-01-05-notes.md`). Update it in place; don't start a new file for the
next session on the same task.

```markdown
---
title: NAS migration to the new box
status: in-progress   # in-progress | waiting | blocked | done
created: 2026-01-05T19:56:00+01:00
updated: 2026-01-07T10:12:00+01:00
---

**Goal** - move all shares off the old NAS without downtime.

**State** - rsync of /photos done and verified (checksums match);
/backups still running, ~40 % at 10:00.

**Dead ends** - NFS export with `all_squash` broke permissions for the
media container; don't retry, use the uid mapping instead.

**Open questions** - keep the old box as an offsite target? (owner)
```

## Staleness

`updated` is the source of truth for freshness; the session brief shows
each file's age and the linter warns after 21 days. Before relying on an old
file, re-check what it claims (is that service still running, is that
blocker still blocking) and correct it. When a task finishes, fold anything
durable into `knowledge/` and delete the file.
