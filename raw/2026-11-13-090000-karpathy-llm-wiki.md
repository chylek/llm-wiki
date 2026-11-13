---
created: 2026-11-13T09:00:00+01:00
status: processed
distilled_into: [llm-wiki-pattern]
---

Idea: instead of RAG over raw documents on every question, let the LLM
*maintain* a wiki - it reads sources once, writes and updates linked
markdown pages, and later questions are answered from the compiled pages.
Karpathy's "LLM Wiki" write-up. Try it with Claude Code + plain git.
