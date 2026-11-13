# Concepts

The ideas behind this repository are written up as notes *inside* the
knowledge base, the same way you would add your own. Read them in this
order:

1. [The LLM wiki pattern](../knowledge/concepts/llm-wiki-pattern.md): why
   an agent-maintained wiki beats re-retrieving raw documents
2. [Capture, then distill](../knowledge/concepts/capture-then-distill.md):
   the two-step intake
3. [Atomic notes](../knowledge/concepts/atomic-notes.md): one idea per
   file, and why that suits agents
4. [Wikilinks and slugs](../knowledge/concepts/wikilinks-and-slugs.md):
   path-free links and the link graph
5. [Memory vs knowledge](../knowledge/concepts/memory-vs-knowledge.md):
   task state that survives interrupted sessions
6. [Hybrid search](../knowledge/concepts/hybrid-search.md): lexical +
   graph + local embeddings
7. [Lint as a guardrail](../knowledge/concepts/lint-as-guardrail.md):
   checks, not prompts, keep conventions
8. [Kanban board as the agent's task queue](../knowledge/concepts/kanban-agent-loop.md):
   bounded autonomy with review
9. [Keeping secrets out of the agent's context](../knowledge/concepts/secrets-out-of-context.md):
   the agent knows which key exists, not its value

## Claude Code terms used here

| Term | Meaning in this repo |
|---|---|
| `CLAUDE.md` | project instructions loaded into every session started in the repo |
| Hook | a command Claude Code runs on an event; `SessionStart` prints the brief into the context |
| Skill | a `SKILL.md` with a description; the agent loads its instructions when a request matches |
| Subagent | an agent with its own context window and tool allowlist (`.claude/agents/`), used for self-contained jobs like the librarian pass |
| Headless mode | `claude -p "<prompt>"`: one non-interactive turn, used by the Planka bridge |
| Session resume | `--session-id <uuid>` starts a named session, `--resume <uuid>` continues it with full history |
| Permission mode | how much the agent may do without asking; headless runs need one that doesn't prompt (see [SECURITY.md](../SECURITY.md)) |
