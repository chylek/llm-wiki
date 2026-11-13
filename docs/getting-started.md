# Getting started

About 15 minutes for the knowledge base, another 20 for the Planka board.

## 1. Prerequisites

| Needed for | What |
|---|---|
| everything | Linux (uses GNU `date`, `find` and `flock`; macOS would need coreutils), bash, git, Python 3.10+ |
| the agent | [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude` on PATH, logged in) |
| semantic search (optional) | [Ollama](https://ollama.com) and ~1.2 GB for the `bge-m3` model |
| task cards (optional) | Docker, for Planka |

## 2. Make it yours

```bash
git clone https://github.com/chylek/llm-wiki.git my-wiki && cd my-wiki
git config core.hooksPath scripts/githooks   # lint before every commit
cp .env.example .env                         # gitignored; fill in later
```

The `knowledge/concepts/` notes and the example capture in `raw/` explain
the system; keep them or delete them once you've read them. Add your own
topic folders next to `concepts/` and list them in `knowledge/README.md`.

## 3. Semantic search (optional)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ollama pull bge-m3
.venv/bin/python3 scripts/vector_index.py reindex
```

Keep the index fresh with a nightly cron entry:

```cron
0 2 * * * cd /path/to/my-wiki && .venv/bin/python3 scripts/vector_index.py reindex
```

Without it, `scripts/search.sh` still works on its lexical and link layers.

## 4. Use it

Start `claude` in the repo. The SessionStart hook prints a brief (active
tasks, lint state, inbox), and `CLAUDE.md` tells the agent how to work here.
Then just talk to it:

| You say | What happens |
|---|---|
| "capture this: <link>" | `capture` skill → new file in `raw/` |
| "process the inbox" | `distill` skill → atomic notes in `knowledge/`, captures marked processed |
| "what do I know about X?" | `kb-search` skill → `scripts/search.sh`, answer with citations |
| "run the librarian" | `librarian` subagent → lint fixes, inbox, orphans, stale-memory report |
| any multi-step task | agent searches first, keeps `memory/<task>.md` current, commits as it goes |

The same scripts work without the agent:

```bash
scripts/capture.sh "an idea"
scripts/inbox.sh
scripts/new-note.sh concepts/my-idea tag1,tag2
scripts/search.sh idea
python3 scripts/kb_lint.py
```

## 5. Task cards from your phone (optional)

Follow [planka-workflow.md](planka-workflow.md).

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
shellcheck scripts/*.sh scripts/planka/*.sh scripts/githooks/pre-commit
.venv/bin/pytest -q
```

CI runs the same checks plus a [gitleaks](https://github.com/gitleaks/gitleaks)
secret scan on every push.
