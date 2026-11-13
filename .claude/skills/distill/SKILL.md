---
name: distill
description: Turn raw/ inbox items into atomic, evergreen knowledge/ notes. Use when the user says "process the inbox", "distill this", "clean up raw/", or when raw/ has unprocessed items worth turning into permanent notes.
---

1. Run `scripts/inbox.sh` to list unprocessed raw items, or work only the
   file(s) the user names.
2. For each item, judge: is there a durable, atomic idea here, or is it noise
   (a link with no insight yet, a duplicate, something already covered)?
   Most captures are noise. Skip those; don't force a note out of nothing.
3. For each idea worth keeping:
   - `scripts/search.sh <term>` first, to find related notes (and avoid
     writing a duplicate).
   - `scripts/new-note.sh <topic>/<slug> <tags>` to scaffold it; topics are
     listed in `knowledge/README.md`.
   - Write the idea in your own words, short, one idea per note. Link related
     notes inline with `[[slug]]`. Never add facts that aren't in the source.
4. Mark the raw source done: `status: processed` and
   `distilled_into: [slug1, slug2]` in its frontmatter.
5. Run `python3 scripts/kb_lint.py`, fix any errors, commit.
6. Report briefly: what was created, what was skipped and why.

Prefer fewer, better notes over covering every raw item.
