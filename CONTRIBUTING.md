# Contributing

Issues and pull requests are welcome. This repo values few moving parts:
a change that removes code is as welcome as one that adds a feature.

## Before you open a PR

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
git config core.hooksPath scripts/githooks
.venv/bin/ruff check . && .venv/bin/ruff format --check .
shellcheck scripts/*.sh scripts/planka/*.sh scripts/githooks/pre-commit
python3 scripts/kb_lint.py --errors-only
.venv/bin/pytest -q
```

CI runs the same, plus a gitleaks secret scan.

## Conventions

- **Python**: 3.10+, ruff-clean (config in `pyproject.toml`), type hints
  on public functions, a docstring on every module and non-trivial
  function. Prefer the standard library; a new dependency needs a reason
  in the PR.
- **Shell**: bash with `set -euo pipefail` (except hooks that must never
  fail), shellcheck-clean, a header comment saying what the script is for
  and how to call it.
- **Comments** explain *why*, not *what*.
- **Configuration** comes from environment variables, documented in
  `.env.example`. Never commit credentials, hostnames, or IDs.
- **Tests**: one small pytest per piece of logic that makes a decision
  (parsing, selection, linting rules). No network in tests.
- **Commits**: one logical change each, message says what and why.
- **Docs**: update `docs/` in the same PR when behaviour or setup changes.

## Using an agent to contribute

Fine and expected; this repo is about agentic workflows. Say so in the PR
template's "Agent involvement" section, and describe what you verified
yourself.
