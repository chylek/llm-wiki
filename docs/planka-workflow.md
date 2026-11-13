# Task cards: Planka + Claude Code

Write a task on a kanban card from your phone; an agent works on it in
this repository and answers in the card's comments. Reply with a comment
and the same agent session continues. The concept is explained in
[kanban-agent-loop](../knowledge/concepts/kanban-agent-loop.md); this page
is the setup and the reference.

Why Planka: it is self-hosted (cards can contain private context), has a
clean REST API with per-user API keys, and a usable mobile web UI. Any
board with comments and lists could be wired the same way;
`planka_board.py`'s `Planka` class is the only Planka-specific part.

## 1. Run Planka

```bash
cd deploy/planka
cp .env.example .env    # set SECRET_KEY (openssl rand -hex 64) and an admin passphrase
docker compose up -d    # http://localhost:3000
```

The compose file binds to localhost only. To use it from a phone, put a
TLS reverse proxy in front and keep it on your LAN or VPN; there is no
reason to expose an agent's task queue to the internet.

## 2. Create the board, the bot user and its API key

One command, run once against the fresh Planka:

```bash
PLANKA_URL=http://localhost:3000 scripts/planka/setup_board.py >> .env
```

It logs in as the admin (password prompted, or `PLANKA_ADMIN_PASSWORD`),
then creates:

- a private project with a board "Tasks" and these lists (names must match
  `LISTS` in `planka_board.py` if you rename them later):

| List | Who moves cards in | Meaning |
|---|---|---|
| Draft | you | still writing; the bridge never touches it |
| Inbox | you | ready for the agent |
| Working | bridge | an agent run is in progress (or was interrupted, and will be retried) |
| Review | bridge | an independent reviewer session checks the result |
| Waiting on you | bridge | your turn: read the reply, comment to continue |
| Done, Parked | **only you** | closed; the agent can't move cards here |

- a bot user `agent` (role *board user*, editor on this board only, terms of
  service accepted), so its comments are distinguishable and its access is
  limited to the one board;
- an API key for the bot (`POST /api/users/<id>/api-key`; Planka shows it
  only once).

and appends `PLANKA_URL`, `PLANKA_BOARD_ID` and `PLANKA_API_KEY` to `.env`.

Optional, in the Planka UI: board labels for topics (the agent picks one
for unlabelled cards), and a card custom field named `Model` (`sonnet`,
`opus`, ...) to choose the model per card.

## 3. Run the bridge

Try one dispatch by hand, with a test card in Inbox:

```bash
scripts/planka/run.sh
```

Then schedule it:

```cron
* * * * * /path/to/my-wiki/scripts/planka/run.sh >> $HOME/.local/log/llm-wiki-planka.log 2>&1
```

Headless runs need Claude Code credentials for the cron user: either log
in with `claude` as that user, or set `CLAUDE_CODE_OAUTH_TOKEN` in `.env`
(from `claude setup-token`). Optional `NOTIFY_COMMAND` pings you when a
card comes back to you (any shell command; the message is `$1`).

## Reference

### What triggers a run

A card gets a worker when it is in **Inbox**, **Working** (a previous run
died) or **Review**, or when it is anywhere except Draft and has a comment
from you that the agent hasn't seen. "Seen" is a timestamp stored per card,
so a comment you add *while* the agent is working is picked up on the next
tick instead of being buried under the reply. Each check is a couple of local API calls, so
polling every minute is cheap; the agent only runs when there is work.

### The reply contract

The agent's final message becomes the comment. The `STATUS:` line must be
last; `ATTACH:` and `LABEL:` lines are recognised anywhere. All are removed
from the visible comment:

| Line | Effect |
|---|---|
| `ATTACH: /abs/path.png` | file uploaded as a card attachment (only from the repo or the temp dir) |
| `LABEL: <name>` | label applied if the card has none |
| `STATUS: waiting` | → Waiting on you (also the default for a missing/unknown status) |
| `STATUS: continue` | stays in Working; the same session runs again next minute |
| `STATUS: review` | → Review; a fresh session checks the work. The default for any turn that changed files |

**Review is the default for changes.** When review was opt-in ("ask if
you're unsure"), the agent almost never asked: two reviews in about 140
replies on the author's own board. Now the rules make `review` the default
whenever a turn changed files, and the bridge enforces it: if the session
used Edit/Write/NotebookEdit outside `memory/` and `raw/` and still replied
`waiting`, the card goes to Review anyway (while the review budget lasts).
Answers and questions to you still come straight back.

`STATUS: done` or `parked` is downgraded to `waiting`: closing is your call.

### Budgets

Per *user turn* (reset whenever you comment): at most `MAX_WORK = 10`
author passes and `MAX_REVIEW = 2` review rounds. A `rework` verdict gives
the author a fresh pass budget, so the worst case is
(MAX_REVIEW + 1) × MAX_WORK = 30 passes. When a budget runs out the card
goes to Waiting on you with a note. Counters are saved *before* each run, so
runs that crash without posting a reply also use them up: a broken card
stops after the budget instead of retrying forever. Counters live in
`$XDG_STATE_HOME/llm-wiki/loops/`.

### The reviewer

A new random session id per round, so it cannot see the author's
reasoning, only the card thread and the repository. It runs without the
Edit/Write tools, is told not to change anything, and ends with
`VERDICT: waiting` (hand it to you) or `VERDICT: rework` (its findings go
into the author's next prompt, with a fresh pass budget). The point is
separation of duties: the session that did the work doesn't approve it.

### Concurrency

At most `MAX_PARALLEL = 3` workers. Each holds an `flock` on
`$XDG_STATE_HOME/llm-wiki/locks/<card>.lock`; the OS drops it if the
worker dies, and the card (still in Working) is picked up again. An
unexpected error inside a worker is posted on the card, which then goes
to Waiting on you. Workers
share one git checkout, which is fine for a personal repo where commits
are small and path-specific; use worktrees if they start to collide.

### Live progress

While the agent runs, one "⏳ Working, N min, M steps" comment shows the
last five tool calls, edited every 20 s and deleted at the end.

### Troubleshooting

| Symptom | Check |
|---|---|
| nothing happens | run `scripts/planka/run.sh` by hand; `missing environment variable` means `.env` is incomplete |
| HTTP 401 | API key wrong, or the bot user hasn't accepted the terms |
| card stuck in Working | a worker is still running (`pgrep -af planka_board`) or crashed; the next tick retries it |
| "Run failed (no result ...)" | the `claude` CLI isn't on cron's PATH or isn't logged in for that user |
| open the agent's session yourself | `claude --resume <uuid>` with the card's session id (`session_id()` in the script) |
