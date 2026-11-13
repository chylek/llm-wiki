# artifacts/

Non-markdown outputs the agent produces: single-file web apps, CSV/JSON
datasets, rendered images, decks. One folder per thing, named after the
slug of the note that describes it (`artifacts/<slug>/`), so
`knowledge/`, `memory/` and `raw/` stay markdown-only (the linter enforces
it). Keep them small; anything regenerable from a script in `scripts/`
should say so in its note.
