#!/usr/bin/env python3
"""Planka board <-> Claude Code bridge: you write cards, an agent answers in comments.

How it works, in one paragraph
------------------------------
A cron job runs this script every minute. With no arguments it is the
*dispatcher*: it reads the board, finds cards that need the agent, and starts
one detached *worker* (``--card <id>``) per card, at most ``MAX_PARALLEL`` at
a time. A worker runs a headless Claude Code session in the repository,
streams its progress into a temporary comment, posts the final answer as a
comment and moves the card to the list named by the answer's last line
(``STATUS: waiting|continue|review``).

Board layout (list names are matched exactly, see ``LISTS``)::

    Draft -> Inbox -> Working -> Review -> Waiting on you -> Done / Parked
      |        |         |          |            |                |
    ignored  new task  agent     independent   your turn       only you
                       running   reviewer                      move cards here

Concepts this file implements (explained in docs/planka-workflow.md):

* **One session per card.** The Claude session id is a UUIDv5 of the card id,
  so a follow-up comment *resumes* the same conversation instead of starting
  cold.
* **Agent loop with a budget.** ``STATUS: continue`` re-runs the same session
  on the next tick, up to ``MAX_WORK`` passes per user turn.
* **Independent review.** ``STATUS: review`` hands the card to a *fresh*
  session that sees only the card and the repo, never the author's
  reasoning, and returns ``VERDICT: waiting`` (ship it) or ``rework``.
* **Human in the loop.** The agent can never move a card to Done or Parked;
  any such request is downgraded to "Waiting on you".

Configuration comes from environment variables only (see ``.env.example``);
nothing secret lives in this file. Stdlib only, so it runs on any Python 3.10+.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, TextIO

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

#: Repository root: the agent's working directory, where CLAUDE.md lives.
REPO = Path(__file__).resolve().parents[2]

#: Where Claude Code keeps session transcripts for this repo. A transcript
#: file existing means the card's session can be resumed.
SESSIONS = Path.home() / ".claude" / "projects" / str(REPO).replace("/", "-")

#: Per-machine runtime state (locks, counters, downloaded attachments).
STATE_ROOT = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "llm-wiki"
LOCKS = STATE_ROOT / "locks"
COUNTERS = STATE_ROOT / "loops"
FILES = STATE_ROOT / "attachments"

TIMEOUT = 2 * 3600  # hard limit for one agent run, seconds
PROGRESS_EVERY = 20  # seconds between edits of the live progress comment
MAX_WORK = 10  # author passes per user turn (STATUS: continue)
MAX_REVIEW = 2  # independent reviews per user turn (STATUS: review)
# ponytail: all workers share one git checkout; give each a worktree if
# parallel commits ever start to clash.
MAX_PARALLEL = 3

#: Board lists by role. Rename here if your board uses other names.
LISTS = {
    "draft": "Draft",
    "inbox": "Inbox",
    "working": "Working",
    "review": "Review",
    "waiting": "Waiting on you",
}

#: Reply status -> list role it moves the card to.
STATUS_TO_LIST = {"waiting": "waiting", "continue": "working", "review": "review"}


def env(name: str, default: str | None = None) -> str:
    """Read a setting from the environment; fail loudly if a required one is missing."""
    value = os.environ.get(name, default)
    if value is None or value == "":
        sys.exit(f"missing environment variable {name} (see .env.example)")
    return value


# --------------------------------------------------------------------------
# Planka REST client (just the handful of calls this bridge needs)
# --------------------------------------------------------------------------


class Planka:
    """Tiny Planka 2.x API client authenticated with a user API key.

    Create the key once as an admin: ``POST /api/users/<bot user id>/api-key``
    (see docs/planka-workflow.md). It is sent as the ``X-Api-Key`` header.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base = base_url.rstrip("/")
        self.key = api_key

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """JSON request against ``/api<path>``; returns the decoded response."""
        req = urllib.request.Request(
            f"{self.base}/api{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Api-Key": self.key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    def download(self, url: str) -> bytes:
        """Fetch an attachment URL (Planka returns absolute URLs)."""
        req = urllib.request.Request(urllib.parse.quote(url, safe=":/"), headers={"X-Api-Key": self.key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def upload(self, card_id: str, path: Path) -> None:
        """Attach a local file to a card (multipart/form-data, built by hand to stay stdlib-only)."""
        boundary = uuid.uuid4().hex
        fields = b"".join(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
            for k, v in (("type", "file"), ("name", path.name))
        )
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = (
            fields
            + f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{path.name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
            + path.read_bytes()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        req = urllib.request.Request(
            f"{self.base}/api/cards/{card_id}/attachments",
            data=body,
            method="POST",
            headers={"X-Api-Key": self.key, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        urllib.request.urlopen(req, timeout=120).close()


# --------------------------------------------------------------------------
# Pure helpers (no I/O, covered by tests/test_planka_board.py)
# --------------------------------------------------------------------------


def session_id(card_id: str) -> str:
    """Deterministic Claude session id for a card: same card -> same conversation."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"planka-card:{card_id}"))


def reply_rules(link_base: str) -> str:
    """The output contract appended to every author prompt.

    The agent's final message *is* the card comment, so the rules are about
    format (phone-sized, links) and about the machine-readable trailer lines
    this script parses in :func:`split_status`.
    """
    links = (
        f"Link repository files as markdown links: [name]({link_base}<repo path>)."
        if link_base
        else "Refer to repository files by their repo-relative path."
    )
    return f"""Your final message is posted verbatim as a comment on the card: write
it for a phone screen, lead with the answer, keep it short. {links}
To attach files (screenshots, renders, PDFs) to the card, put one line
`ATTACH: <absolute path>` per file just before the last line.
Don't wait on background tasks: run things in the foreground; only your final
message is posted, so it must hold the whole answer.
The last line must be exactly one of:
- `STATUS: waiting`  - your turn is over, the user acts next.
- `STATUS: continue` - not finished; you are re-run in this same session
  (up to {MAX_WORK} passes per user turn), put a short progress note above.
- `STATUS: review`   - you think it's done but want an independent reviewer
  to check (up to {MAX_REVIEW} reviews); it hands the card to the user or
  sends notes back to you.
Never move a card to Done or Parked: only the user does that."""


REVIEW_RULES = """You are an independent reviewer. The author's session is not visible to you:
judge from the card below and the real state of the repository (check the
claims, run the checks; do NOT modify anything). The bridge strips the author's
STATUS/ATTACH/LABEL trailer lines before posting, so don't expect them in the
thread. Reply with short findings for
a phone screen, then as the last line exactly one of: `VERDICT: waiting` (good,
hand it to the user) or `VERDICT: rework` (the findings must then say
concretely what to change)."""


def split_status(reply: str) -> tuple[str, str, list[str], str | None]:
    """Parse the agent's reply into (comment text, status, attachments, label).

    Trailer lines (``STATUS:``, ``ATTACH:``, ``LABEL:``) are removed from the
    visible comment. A missing or unknown status means "waiting", and
    ``done``/``parked`` are downgraded to "waiting" as well: closing a card
    is the human's decision, whatever the model says.
    """
    lines = reply.rstrip().splitlines()
    status = "waiting"
    last = lines[-1].strip().lower() if lines else ""
    if last.startswith("status:"):
        lines.pop()
        wanted = last.split(":", 1)[1].strip()
        status = wanted if wanted in STATUS_TO_LIST else "waiting"
    attach = [ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("ATTACH:")]
    label = next((ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("LABEL:")), None)
    text = "\n".join(ln for ln in lines if not ln.startswith(("ATTACH:", "LABEL:"))).rstrip()
    return text, status, attach, label


def parse_verdict(out: str) -> tuple[str, str]:
    """Reviewer output -> (verdict, findings). Anything unclear means "waiting"."""
    m = re.search(r"VERDICT:\s*(waiting|done|rework)\s*$", out.rstrip(), re.IGNORECASE)
    if not m:
        return "waiting", out.rstrip()
    verdict = m.group(1).lower()
    return ("rework" if verdict == "rework" else "waiting"), out[: m.start()].rstrip()


def step_line(block: dict[str, Any]) -> str:
    """One short progress line for a ``tool_use`` block from the stream."""
    inp = block.get("input", {})
    keys = ("description", "command", "file_path", "pattern", "query", "url", "prompt")
    detail = next((str(inp[k]) for k in keys if k in inp), "")
    return f"- {block['name']}: {' '.join(detail.split())[:90]}".rstrip(": ")


def needs_agent(list_role: str | None, comments: list[dict[str, Any]], bot_id: str) -> bool:
    """Does a card in this list, with these comments, need an agent run?

    Yes when it is new (Inbox), was interrupted (Working), awaits review
    (Review), or anywhere else when the newest comment isn't the bot's
    (the user replied). Draft and unknown lists are never touched.
    """
    if list_role in (None, "draft"):
        return False
    if list_role in ("inbox", "working", "review"):
        return True
    return bool(comments) and comments[-1]["userId"] != bot_id


# --------------------------------------------------------------------------
# Runtime state: per-card locks and pass counters
# --------------------------------------------------------------------------


def lock(card_id: str) -> TextIO | None:
    """Non-blocking per-card file lock. Keep the returned file open to hold it.

    Returns None if another worker already holds it. The OS releases the lock
    when the process dies, so a crashed worker never leaves a card stuck.
    """
    LOCKS.mkdir(parents=True, exist_ok=True)
    f = open(LOCKS / f"{card_id}.lock", "w")  # noqa: SIM115 - lifetime = lock lifetime
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return None


def fresh_counters() -> dict[str, Any]:
    return {"work": 0, "review": 0, "notes": ""}


def load_counters(card_id: str) -> dict[str, Any]:
    try:
        return json.loads((COUNTERS / f"{card_id}.json").read_text())
    except (OSError, ValueError):
        return fresh_counters()


def save_counters(card_id: str, counters: dict[str, Any]) -> None:
    COUNTERS.mkdir(parents=True, exist_ok=True)
    (COUNTERS / f"{card_id}.json").write_text(json.dumps(counters))


# --------------------------------------------------------------------------
# The bridge
# --------------------------------------------------------------------------


class Bridge:
    """Board-level operations shared by the dispatcher and the workers."""

    def __init__(self) -> None:
        self.planka = Planka(env("PLANKA_URL"), env("PLANKA_API_KEY"))
        self.board_id = env("PLANKA_BOARD_ID")
        self.link_base = os.environ.get("LINK_BASE", "")
        self.notify_cmd = os.environ.get("NOTIFY_COMMAND", "")
        self.permission_mode = os.environ.get("CLAUDE_PERMISSION_MODE", "auto")
        self.bot_id = self.planka.call("GET", "/users/me")["item"]["id"]

    # -- board reading ------------------------------------------------------

    def board(self) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
        """-> (board 'included' payload, role -> list id, list id -> role)."""
        inc = self.planka.call("GET", f"/boards/{self.board_id}")["included"]
        by_name = {lst["name"]: lst["id"] for lst in inc["lists"] if lst.get("name")}
        role_to_id = {role: by_name[name] for role, name in LISTS.items() if name in by_name}
        return inc, role_to_id, {v: k for k, v in role_to_id.items()}

    def comments(self, card_id: str) -> list[dict[str, Any]]:
        items = self.planka.call("GET", f"/cards/{card_id}/comments")["items"]
        return sorted(items, key=lambda c: c["createdAt"])

    def move(self, card_id: str, list_id: str) -> None:
        self.planka.call("PATCH", f"/cards/{card_id}", {"listId": list_id, "position": 65536})

    def comment(self, card_id: str, text: str) -> None:
        self.planka.call("POST", f"/cards/{card_id}/comments", {"text": text})

    def fetch_attachments(self, card_id: str) -> list[Path]:
        """Download the card's file attachments not seen before; return their local paths."""
        folder = FILES / card_id
        folder.mkdir(parents=True, exist_ok=True)
        new = []
        for att in self.planka.call("GET", f"/cards/{card_id}")["included"]["attachments"]:
            path = folder / f"{att['id']}-{Path(att['name']).name}"  # .name strips any path parts
            if att["type"] != "file" or path.exists():
                continue
            path.write_bytes(self.planka.download(att["data"]["url"]))
            new.append(path)
        return new

    def model_for(self, card_id: str) -> str:
        """The card's optional custom field "Model" (e.g. ``sonnet``); empty = CLI default."""
        inc = self.planka.call("GET", f"/cards/{card_id}")["included"]
        field = next((f for f in inc["customFields"] if f["name"] == "Model"), None)
        if field is None:
            return ""
        return next(
            (v["content"].strip() for v in inc["customFieldValues"] if v["customFieldId"] == field["id"]),
            "",
        )

    def notify(self, card: dict[str, Any], status: str) -> None:
        """Optional push notification when a card comes back to the user (best effort).

        ``NOTIFY_COMMAND`` is any shell command; the message arrives as ``$1``,
        e.g. ``NOTIFY_COMMAND='apprise -b "$1" tgram://...'``.
        """
        if self.notify_cmd and status == "waiting":
            msg = f"Waiting on you: {card['name']}\n{self.planka.base}/cards/{card['id']}"
            subprocess.run(["sh", "-c", self.notify_cmd, "_", msg], stdin=subprocess.DEVNULL, check=False)

    # -- running the agent ------------------------------------------------

    def run_claude(self, card_id: str, prompt: str, sid: str, resume: bool, model: str = "") -> str:
        """Run one headless Claude Code turn and return its final text.

        Output is consumed as ``stream-json`` so progress can be shown while
        it runs: every ``PROGRESS_EVERY`` seconds a single "Working..." comment
        is created or edited with the latest tool calls, and deleted at the end.
        """
        cmd = [
            "claude", "-p", prompt,
            "--resume" if resume else "--session-id", sid,
            "--permission-mode", self.permission_mode,
            "--output-format", "stream-json", "--verbose",
        ]  # fmt: skip
        if model:
            cmd += ["--model", model]
        proc = subprocess.Popen(
            cmd, cwd=REPO, stdout=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        killer = threading.Timer(TIMEOUT, proc.kill)
        killer.start()
        start, last_post, steps, shown = time.time(), 0.0, [], 0
        progress_id: str | None = None
        result: dict[str, Any] | None = None
        earlier: list[str] = []  # text of results before the last one
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    # A late background-task notification can start another turn,
                    # whose result would otherwise replace the real answer.
                    if result and not result.get("is_error"):
                        earlier.append(split_status(result["result"])[0])
                    result = event
                if event.get("type") == "assistant":
                    steps += [step_line(b) for b in event["message"].get("content", []) if b.get("type") == "tool_use"]
                if len(steps) > shown and time.time() - last_post >= PROGRESS_EVERY:
                    shown, last_post = len(steps), time.time()
                    text = (
                        f"⏳ Working, {int((last_post - start) / 60)} min, {len(steps)} steps. Latest:\n"
                        + "\n".join(steps[-5:])
                    )
                    with contextlib.suppress(OSError):  # progress is cosmetic; never fail the run over it
                        if progress_id is None:
                            progress_id = self.planka.call("POST", f"/cards/{card_id}/comments", {"text": text})[
                                "item"
                            ]["id"]
                        else:
                            self.planka.call("PATCH", f"/comments/{progress_id}", {"text": text})
            proc.wait()
        finally:
            killer.cancel()
            if progress_id:
                with contextlib.suppress(OSError):
                    self.planka.call("DELETE", f"/comments/{progress_id}")
        if result is None:
            return f"Run failed (no result, exit code {proc.returncode}); session {sid}.\n\nSTATUS: waiting"
        if result.get("is_error"):
            return f"Run failed: {result.get('result')}\n\nSTATUS: waiting"
        return "\n\n".join([*earlier, result["result"]])

    # -- prompts ------------------------------------------------------------

    def first_prompt(self, card: dict[str, Any], comments: list[dict[str, Any]], files: list[Path]) -> str:
        """Prompt for a card's first run: the whole card plus the working rules."""
        thread = "\n\n".join(f"[comment] {c['text']}" for c in comments)
        attached = ("\n\nAttachments on the card (Read them):\n" + "\n".join(map(str, files))) if files else ""
        return f"""A task card from the user's Planka board (card {card["id"]}).
Nobody watches this session live; later comments on the card resume it.

Title: {card["name"]}
Description:
{card.get("description") or "(none)"}
{thread}{attached}

Work on it as in an interactive session: CLAUDE.md applies (search the
knowledge base first, keep memory/ current, commit). If you need a decision or
information from the user, ask for it and stop.

{reply_rules(self.link_base)}"""

    def followup_prompt(self, comments: list[dict[str, Any]], files: list[Path]) -> str:
        """Prompt for a resumed session: only what the user said since the bot's last comment."""
        last_bot = max((i for i, c in enumerate(comments) if c["userId"] == self.bot_id), default=-1)
        new = "\n\n".join(c["text"] for c in comments[last_bot + 1 :]) or "(no new comment)"
        attached = ("\n\nNew attachments on the card (Read them):\n" + "\n".join(map(str, files))) if files else ""
        return f"The user replied on the card:\n\n{new}{attached}\n\n{reply_rules(self.link_base)}"

    # -- worker -------------------------------------------------------------

    def work(self, card_id: str) -> None:
        """Worker entry point: handle one card while holding its lock."""
        held = lock(card_id)
        if held is None:
            return  # another worker has it
        inc, role_to_id, id_to_role = self.board()
        card = next((c for c in inc["cards"] if c["id"] == card_id), None)
        if card is None:
            return
        role = id_to_role.get(card["listId"])
        comments = self.comments(card_id)
        if not needs_agent(role, comments, self.bot_id):
            return  # answered or moved since the dispatcher looked

        # A "user turn" starts when the card is new or the user just replied:
        # that resets the pass/review budget.
        user_turn = role == "inbox" or not comments or comments[-1]["userId"] != self.bot_id
        counters = fresh_counters() if user_turn else load_counters(card_id)
        try:
            model = self.model_for(card_id)
        except OSError:
            model = ""
        if role == "review":
            return self.review(card, comments, role_to_id, counters, model)

        self.move(card_id, role_to_id["working"])
        counters["work"] += 1
        sid = session_id(card_id)
        resume = (SESSIONS / f"{sid}.jsonl").exists()
        labels = {lb["name"]: lb["id"] for lb in inc["labels"]}
        labelled = {cl["cardId"] for cl in inc["cardLabels"]}
        ask_label = (
            ""
            if card_id in labelled or not labels
            else f"\nThe card has no label yet: add one line `LABEL: <name>` before the last line, "
            f"choosing from: {', '.join(labels)}."
        )

        if user_turn or not resume:
            files = self.fetch_attachments(card_id)
            prompt = self.followup_prompt(comments, files) if resume else self.first_prompt(card, comments, files)
        elif counters["notes"]:  # back from a "rework" review
            prompt = f"The independent reviewer sent this back:\n\n{counters['notes']}\n\nFix it.\n\n"
            prompt += reply_rules(self.link_base)
        else:  # a STATUS: continue pass
            prompt = "Continue the task: re-check your work against the card and finish what is left.\n\n"
            prompt += reply_rules(self.link_base)
        counters["notes"] = ""
        budget = f"(Pass {counters['work']}/{MAX_WORK}, reviews so far {counters['review']}/{MAX_REVIEW}.)"
        prompt += f"{ask_label}\n\n{budget}"

        text, status, attach, label = split_status(self.run_claude(card_id, prompt, sid, resume, model))

        # Budgets: when exhausted, hand the card to the human instead of looping.
        if status == "continue" and counters["work"] >= MAX_WORK:
            status, text = "waiting", text + f"\n\n(Limit of {MAX_WORK} passes reached, handing over.)"
        if status == "review" and counters["review"] >= MAX_REVIEW:
            status, text = "waiting", text + f"\n\n(Limit of {MAX_REVIEW} reviews reached, handing over.)"
        if status == "continue":
            text = f"🔁 Pass {counters['work']}/{MAX_WORK}\n\n{text}"
        save_counters(card_id, counters)

        if label in labels and card_id not in labelled:
            self.planka.call("POST", f"/cards/{card_id}/card-labels", {"labelId": labels[label]})
        for path in attach:
            try:
                self.planka.upload(card_id, Path(path))
            except OSError as exc:  # missing file or upload error: say so, keep going
                text += f"\n\n(Couldn't attach {path}: {exc})"
        self.comment(card_id, text)
        self.move(card_id, role_to_id.get(STATUS_TO_LIST[status], role_to_id["waiting"]))
        self.notify(card, status)
        print(f"card {card_id} -> {status}", flush=True)

    def review(
        self,
        card: dict[str, Any],
        comments: list[dict[str, Any]],
        role_to_id: dict[str, str],
        counters: dict[str, Any],
        model: str,
    ) -> None:
        """Independent review: a fresh session per round, its verdict moves the card."""
        counters["review"] += 1
        thread = "\n\n".join(f"[{'author' if c['userId'] == self.bot_id else 'user'}] {c['text']}" for c in comments)
        prompt = (
            f"{REVIEW_RULES}\n\nCard {card['id']}\nTitle: {card['name']}\nDescription:\n"
            f"{card.get('description') or '(none)'}\n\n"
            f"Thread (the last author comment is the claim to check):\n{thread}"
        )
        # A new random session each round: the reviewer must not inherit context.
        out = self.run_claude(card["id"], prompt, str(uuid.uuid4()), False, model)
        verdict, findings = parse_verdict(out)
        self.comment(card["id"], f"🔍 Review {counters['review']}/{MAX_REVIEW}: {verdict}\n\n{findings}")
        if verdict == "rework":  # notes go to the author's next pass, with a fresh pass budget
            counters["notes"], counters["work"] = findings, 0
        save_counters(card["id"], counters)
        self.move(card["id"], role_to_id["working" if verdict == "rework" else "waiting"])
        self.notify(card, verdict)
        print(f"card {card['id']} review -> {verdict}", flush=True)

    # -- dispatcher ---------------------------------------------------------

    def dispatch(self) -> None:
        """Start a detached worker for each card that needs one, up to MAX_PARALLEL."""
        inc, _, id_to_role = self.board()
        todo, running = [], 0
        for card in inc["cards"]:
            role = id_to_role.get(card["listId"])
            if role in (None, "draft") or not needs_agent(role, self.comments(card["id"]), self.bot_id):
                continue
            held = lock(card["id"])
            if held is None:
                running += 1  # a worker is already on it
            else:
                held.close()  # free again: the worker takes it
                todo.append(card["id"])
        for card_id in todo[: max(0, MAX_PARALLEL - running)]:
            # start_new_session: the worker outlives this short dispatcher run.
            subprocess.Popen(
                [sys.executable, __file__, "--card", card_id],
                cwd=REPO,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"started worker for card {card_id}", flush=True)


def main(argv: list[str]) -> int:
    bridge = Bridge()
    if argv[:1] == ["--card"] and len(argv) == 2:
        bridge.work(argv[1])
    elif not argv:
        bridge.dispatch()
    else:
        print("usage: planka_board.py [--card <card id>]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
