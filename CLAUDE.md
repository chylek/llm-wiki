# Working instructions for the agent

This repository is a knowledge base that you, the agent, help maintain.
These rules are loaded into every Claude Code session started here,
including the headless sessions the Planka bridge starts for task cards.

## Look it up first

Before researching a topic, answering a question about the owner's setup,
or starting a task that touches it, run `scripts/search.sh <term>` (try a
second term if the first comes up thin). It combines grep, one hop of
`[[wikilinks]]`, and semantic similarity over local embeddings; the last
finds notes that share no words with the query. It also covers `memory/`,
so earlier dead ends surface before they get retried.

## Write it down as you go

Record progress, new facts, decisions and dead ends while you work, not at
the end: a session can be interrupted at any point and the next one starts
with only what's written down.

- Task state goes into `memory/<task-slug>.md` (format in
  `memory/README.md`): goal, current state, dead ends, open questions.
  Bump `updated` on every edit. Check `updated` before trusting a memory
  file; correct or delete what has gone stale.
- Durable, evergreen ideas go into `knowledge/<topic>/<slug>.md`, one idea
  per note (`scripts/new-note.sh`, conventions in `knowledge/README.md`).
- Unsorted input goes into `raw/` (`scripts/capture.sh`); the `distill`
  skill turns it into notes later.
- A script you'd plausibly run again goes into `scripts/`, not `/tmp`.
- Non-markdown outputs (HTML, CSV, images) go into `artifacts/<slug>/`.

## Version control

Commit each meaningful change as you make it: a note, a memory update, a
script. Stage specific paths (never `git add -A`), check `git diff --staged`
first, and write messages that say what changed and why. Run
`python3 scripts/kb_lint.py` if the pre-commit hook isn't enabled.

## Never

- Commit credentials. Secrets live in `.env` (gitignored).
- Print a secret. `scripts/secrets.sh` lists which keys exist (without
  values); use a value only inside a command, `$(scripts/secrets.sh KEY)`,
  so it never appears in output. Never `cat`, `grep` or `echo` `.env`.
- Send email, post publicly, or push to a remote unless the owner asked for
  that specific action.
