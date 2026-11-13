---
title: Keeping secrets out of the agent's context
tags: [agents,security,secrets]
created: 2026-11-13T13:00:00+01:00
updated: 2026-11-13T13:00:00+01:00
---

# Keeping secrets out of the agent's context

An agent with a shell needs credentials (API keys, tokens) to do real work,
but everything a command prints lands in the model's context: it's sent
to the model provider, kept in the session transcript, and can be echoed
back into a note or a card comment by accident.

The rule here is **the agent may know a secret exists, not what it is**:

- `scripts/secrets.sh` with no arguments lists key names, a description
  and whether each is set, never the values. That's enough to pick the
  right credential.
- A value is only ever used inside command substitution,
  `curl -H "X-Api-Key: $(scripts/secrets.sh PLANKA_API_KEY)" ...`, so the
  shell passes it to the command and it never shows up in output.
- `.claude/settings.json` denies the Read/Edit tools on `.env`, and
  `CLAUDE.md` forbids `cat`/`grep` on it. That's a guardrail against
  accidents, not a sandbox: a determined shell command could still read
  the file (see `SECURITY.md`).

Long-running code like the Planka bridge doesn't use the script at all: it
gets its settings from the environment its cron wrapper loads. Related:
[[lint-as-guardrail]] (checks over prompts), [[kanban-agent-loop]].
