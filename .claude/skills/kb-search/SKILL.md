---
name: kb-search
description: Search knowledge/, memory/ and raw/ for a topic and report what the knowledge base already contains. Use when the user asks "what do I know about X" or "have I written about X before", before starting new research, and before any task touching the user's own setup, where a note may already hold the procedure or a recorded dead end.
---

Run `scripts/search.sh <term>`; try a couple of related terms (synonyms,
singular/plural) if the first comes up thin.

The output has up to three sections:

- direct matches: the term appears in the text or in frontmatter `tags`
- `related via [[wikilinks]]`: notes one hop away in the link graph
- `related via semantic similarity`: notes close in meaning per local
  embeddings, even with no shared words

Treat both "related" groups as leads, not answers: check that they are
relevant before citing them. The semantic section is silently missing when
the embedding service is down; that just means reduced coverage.

Read matching files in full, not only the grep context lines, then answer
from what is actually there, citing note paths. If nothing is found, say
so: "the knowledge base has nothing on this" is a useful answer.
