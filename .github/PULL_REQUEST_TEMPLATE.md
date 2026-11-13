## What and why

<!-- One or two sentences: what changes, and the problem it solves. Link the issue: Closes #123 -->

## How it was checked

<!-- Commands you ran and what you saw. "Ran it against a test board" beats "should work". -->

- [ ] `ruff check . && ruff format --check .`
- [ ] `shellcheck scripts/*.sh scripts/planka/*.sh scripts/githooks/pre-commit`
- [ ] `python3 scripts/kb_lint.py --errors-only`
- [ ] `pytest -q`

## Checklist

- [ ] No credentials, hostnames, IDs or personal data in code, docs or example notes
- [ ] New settings are read from the environment and listed in `.env.example`
- [ ] Docs updated (`docs/`, `README.md`) if behaviour or setup changed
- [ ] Non-obvious code has a comment explaining *why*

## Agent involvement

<!-- Optional but welcome in this repo: was this written with an agent? What did you verify by hand? -->
