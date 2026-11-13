---
title: Wikilinks and slugs
tags: [knowledge-management,links]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T09:30:00+01:00
---

# Wikilinks and slugs

Notes link with `[[slug]]`, where the slug is the file name without `.md`.
Slugs are unique across **all** topic folders, so a link never contains a
path and a note can move between folders without breaking anything.

The links form a graph that `scripts/search.sh` walks one hop out from
every direct hit: notes connected to a match show up even when they share
no words with the query ([[hybrid-search]]). The linter rejects broken and
path-style links and reports orphans with no inbound link
([[lint-as-guardrail]]). Small [[atomic-notes]] make each link meaningful.
