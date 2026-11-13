---
title: The LLM wiki pattern
tags: [llm,knowledge-management,agents]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T09:30:00+01:00
---

# The LLM wiki pattern

Most "chat with your documents" setups use retrieval-augmented generation
(RAG): every question re-reads raw sources and the model re-derives the
answer from scratch. Nothing accumulates.

The LLM wiki pattern ([Karpathy, April 2026](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f))
flips that: the agent reads a source **once** and *compiles* it into a
persistent wiki of interlinked markdown pages, updating existing pages
instead of piling up new ones. Later questions are answered from the
compiled pages, so knowledge compounds. The human curates sources and asks
questions; the agent does the writing, linking and upkeep.

This repository implements the pattern with three folders:

- `raw/`: unfiltered input ([[capture-then-distill]])
- `knowledge/`: compiled, [[atomic-notes]] connected by [[wikilinks-and-slugs]]
- `memory/`: task state, a deliberate addition ([[memory-vs-knowledge]])

and adds what a wiki needs to survive months of agent edits: retrieval
([[hybrid-search]]), mechanical checks ([[lint-as-guardrail]]), and a way
to hand the agent work from a phone ([[kanban-agent-loop]]).
