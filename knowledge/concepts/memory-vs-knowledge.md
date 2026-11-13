---
title: Memory vs knowledge
tags: [agents,memory,context]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T09:30:00+01:00
---

# Memory vs knowledge

An agent session starts with an empty context window. Whatever isn't
written down is lost when it ends, or when it gets interrupted halfway.
So the repo separates two kinds of written state:

| | `knowledge/` | `memory/` |
|---|---|---|
| holds | what is durably true | where a task stands right now |
| lifetime | evergreen, edited in place | until the task ends |
| example | "how the backup rotation works" | "rsync done, /backups at 40 %, NFS squash was a dead end" |

Memory files record **dead ends** on purpose: the most expensive mistake an
agent makes is confidently retrying something that already failed. The
`updated` timestamp tells the next session how far to trust the file; the
session-start brief lists every active file with its age, so a fresh
session sees open work without searching. When the task ends, its durable
parts are distilled into knowledge and the file is deleted.

This is the addition to the [[llm-wiki-pattern]] that makes long,
interruptible tasks like [[kanban-agent-loop]] cards work.
