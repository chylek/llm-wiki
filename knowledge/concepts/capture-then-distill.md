---
title: Capture, then distill
tags: [workflow,knowledge-management]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T09:30:00+01:00
---

# Capture, then distill

Two separate steps with opposite goals:

1. **Capture** is instant and judgment-free: `scripts/capture.sh "..."`
   writes the text to `raw/` with `status: unprocessed`. If filing a thought
   requires deciding where it goes, it doesn't get filed.
2. **Distill** happens later, in batch, with more context: the `distill`
   skill (or the `librarian` agent) reads the inbox, discards noise, and
   rewrites what's durable as [[atomic-notes]]. The raw file records
   `distilled_into: [...]`, so provenance is kept.

Most captures never become notes. That is the filter working, not a
failure. Part of [[llm-wiki-pattern]].
