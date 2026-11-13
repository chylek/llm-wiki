---
title: Lint as a guardrail for agent edits
tags: [agents,quality,automation]
created: 2026-11-13T09:30:00+01:00
updated: 2026-11-13T09:30:00+01:00
---

# Lint as a guardrail for agent edits

An agent editing a wiki hundreds of times will drift from its conventions:
a link to a renamed note, a missing timestamp, a PNG dropped into
`knowledge/`. Prompts alone don't prevent drift; checks do.

`scripts/kb_lint.py` splits findings in two:

- **Errors** (broken/path-style links, missing frontmatter, duplicate
  slugs, misplaced files) block the commit via the pre-commit hook and CI.
- **Warnings** (stale or finished memory files, orphan notes, oversized
  notes, old unprocessed captures) never block; they feed the session
  brief, so the next session sees the housekeeping that is due.

It is stdlib-only on purpose: the linter must not depend on the same
virtualenv whose breakage it may need to report. See
[[wikilinks-and-slugs]] and [[atomic-notes]] for the rules it checks, and
[[secrets-out-of-context]] for the same idea applied to credentials.
