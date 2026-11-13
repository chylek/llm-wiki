---
title: Kanban board as the agent's task queue
tags: [agents,planka,automation,human-in-the-loop]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T17:40:00+01:00
---

# Kanban board as the agent's task queue

Chat is a poor interface for work that takes an hour and needs your input
twice. A kanban board is better: each task is a card with its own thread,
status is visible at a glance, and you can add work from a phone.

`scripts/planka/planka_board.py` connects a self-hosted Planka board to
headless Claude Code:

- **Card = session.** The session id is derived from the card id, so every
  comment you add resumes the same conversation.
- **Lists = state machine.** Draft (ignored) → Inbox → Working → Review →
  Waiting on you → Done/Parked. The agent's reply ends with
  `STATUS: waiting|continue|review`, and the bridge moves the card.
- **Bounded autonomy.** `continue` re-runs the agent (max 10 passes);
  `review` asks a *fresh* session with no access to the author's reasoning
  to check the result against the card (max 2 rounds). Review is the
  default whenever a turn changed files, enforced by the bridge: agents
  rarely volunteer that they might be wrong. Budgets prevent runaway loops.
- **Human owns closure.** The agent can't move cards to Done or Parked.

Long cards work because the agent records progress in
[[memory-vs-knowledge]] as it goes. Details in `docs/planka-workflow.md`.
Part of [[llm-wiki-pattern]].
