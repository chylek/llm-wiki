"""Bridge.work() end to end against an in-memory fake Planka, with the agent stubbed out."""

import itertools
import os

import planka_board as pb
import pytest

BOT, USER = "bot", "user"
LISTS = {role: f"L-{role}" for role in pb.LISTS}


class FakePlanka:
    """Just enough of the Planka API for one board with one card."""

    def __init__(self, list_role):
        self.clock = itertools.count(1)
        self.card = {"id": "c1", "name": "Task", "description": "do it", "listId": LISTS[list_role]}
        self.comments = []
        self.base = "http://planka.test"

    def add_comment(self, user, text):
        item = {"id": f"m{len(self.comments)}", "userId": user, "text": text,
                "createdAt": f"2026-01-01T00:00:{next(self.clock):02d}.000Z"}  # fmt: skip
        self.comments.append(item)
        return item

    def call(self, method, path, body=None):
        if path.startswith("/boards/"):
            lists = [{"id": i, "name": pb.LISTS[r]} for r, i in LISTS.items()]
            return {"included": {"lists": lists, "cards": [self.card], "labels": [], "cardLabels": []}}
        if path == "/cards/c1/comments":
            if method == "POST":
                return {"item": self.add_comment(BOT, body["text"])}
            return {"items": list(self.comments)}
        if path == "/cards/c1" and method == "PATCH":
            self.card["listId"] = body["listId"]
            return {}
        if path == "/cards/c1":
            return {"included": {"attachments": [], "customFields": [], "customFieldValues": []}}
        raise AssertionError(f"unexpected call {method} {path}")

    def role(self):
        return next(r for r, i in LISTS.items() if i == self.card["listId"])


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    for name in ("LOCKS", "COUNTERS", "FILES", "SESSIONS"):
        monkeypatch.setattr(pb, name, tmp_path / name)

    def make(list_role, agent):
        b = object.__new__(pb.Bridge)  # skip __init__: no env, no network
        b.planka, b.bot_id, b.board_id, b.link_base, b.notify_cmd = FakePlanka(list_role), BOT, "b1", "", ""
        b.run_claude = lambda card_id, prompt, *a, **kw: agent(b.planka, prompt)
        return b

    return make


def test_inbox_card_gets_answer_and_waits(bridge):
    b = bridge("inbox", lambda planka, prompt: "Done.\nSTATUS: waiting")
    b.planka.add_comment(USER, "details")
    b.work("c1")
    assert b.planka.comments[-1]["text"] == "Done."
    assert b.planka.role() == "waiting"
    seen = pb.load_counters("c1")["seen"]
    assert not pb.needs_agent("waiting", b.planka.comments, BOT, seen)


def test_comment_written_during_the_run_is_picked_up(bridge):
    def agent(planka, prompt):
        planka.add_comment(USER, "oh, and also X")  # arrives while the agent works
        return "Done.\nSTATUS: waiting"

    b = bridge("inbox", agent)
    b.work("c1")
    seen = pb.load_counters("c1")["seen"]
    assert pb.needs_agent("waiting", b.planka.comments, BOT, seen)
    assert [c["text"] for c in pb.new_user_comments(b.planka.comments, BOT, seen)] == ["oh, and also X"]


def test_crash_is_reported_and_not_retried(bridge):
    def agent(planka, prompt):
        raise RuntimeError("boom")

    b = bridge("inbox", agent)
    with pytest.raises(RuntimeError):
        b.work("c1")
    assert "boom" in b.planka.comments[-1]["text"]
    assert b.planka.role() == "waiting"
    assert not pb.needs_agent("waiting", b.planka.comments, BOT, pb.load_counters("c1")["seen"])


def test_spent_budget_in_working_hands_over_without_running(bridge):
    def agent(planka, prompt):
        raise AssertionError("must not run")

    b = bridge("working", agent)
    pb.save_counters("c1", {**pb.fresh_counters(), "work": pb.MAX_WORK})
    b.work("c1")
    assert b.planka.role() == "waiting"


def test_continue_stays_in_working_and_counts(bridge):
    b = bridge("inbox", lambda planka, prompt: "half way\nSTATUS: continue")
    b.work("c1")
    assert b.planka.role() == "working"
    assert b.planka.comments[-1]["text"].startswith("🔁 Pass 1/")
    b.work("c1")  # next tick: same turn, budget keeps counting
    assert pb.load_counters("c1")["work"] == 2


def test_attachable(tmp_path):
    inside = pb.REPO / "README.md"
    assert pb.attachable(str(inside)) == inside.resolve()
    assert pb.attachable("/etc/passwd") is None
    assert pb.attachable(str(pb.REPO / "scripts")) is None  # not a file
    env_file = tmp_path / ".env"
    env_file.write_text("X=1")
    assert pb.attachable(str(env_file)) is None


def test_agent_env_drops_bridge_settings(monkeypatch):
    monkeypatch.setenv("PLANKA_API_KEY", "x")
    monkeypatch.setenv("NOTIFY_COMMAND", "x")
    env = pb.agent_env()
    assert "PLANKA_API_KEY" not in env and "NOTIFY_COMMAND" not in env
    assert env.get("PATH") == os.environ["PATH"]
