# Security

## Reporting

Please report vulnerabilities privately through
[GitHub security advisories](https://github.com/chylek/llm-wiki/security/advisories/new),
not as a public issue.

## Threat model, briefly

This project runs an AI agent **unattended** with write access to a git
repository, triggered by text on a kanban board. Treat it accordingly:

- **Board access = agent access.** Anyone who can create or comment on
  cards on the watched board can instruct the agent. Keep the board private
  to you, and Planka off the public internet (LAN/VPN + TLS proxy).
- **Prompt injection.** Card attachments, web pages and captured text are
  untrusted input that the agent reads. A malicious document can try to
  steer it. Mitigations here: the agent can't close cards, push, or send
  messages unless explicitly asked (`CLAUDE.md`); loop and review budgets
  are enforced in code; every change is a git commit you can inspect and
  revert.
- **Permission mode.** `CLAUDE_PERMISSION_MODE` defaults to `auto`, where
  Claude Code's safety classifier gates actions instead of interactive
  prompts. Use a stricter mode plus an allowlist in `.claude/settings.json`
  if you prefer, or run the bridge as a dedicated low-privilege user,
  ideally in a container or VM.
- **Secrets.** All credentials come from `.env` (gitignored) or the
  environment. Don't store secrets in notes: notes are read into model
  context and may be sent to the model provider.
- **Data leaves the machine** when the agent reads it: card text, notes and
  files the agent opens are sent to the model API. Embeddings for search
  are computed locally.
