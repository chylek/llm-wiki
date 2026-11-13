---
title: Hybrid search
tags: [search,embeddings,rag]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T09:30:00+01:00
---

# Hybrid search

`scripts/search.sh` answers "what do we already know about X" in three
layers, each covering the previous one's blind spot:

1. **Lexical**: grep for the term in text and frontmatter tags. Exact,
   explainable, misses synonyms.
2. **Graph**: notes one [[wikilinks-and-slugs]] hop from a lexical hit.
   Finds context the author connected by hand.
3. **Semantic**: embeddings via a local Ollama model (`bge-m3`) stored in
   Chroma. Finds notes with no shared words at all. Notes are chunked at
   `##` headings and re-embedded only when a chunk's hash changes.

The semantic layer is best-effort: if Ollama is down the search prints the
first two layers and carries on. A search that fails because a side
service is down trains people (and agents) to stop searching.

The agent's instructions make search the first step of every task, so
earlier work and dead ends ([[memory-vs-knowledge]]) surface before
anything is redone.
