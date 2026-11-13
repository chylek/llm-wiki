"""The parts of the Planka bridge that decide things: reply parsing and card selection."""

import planka_board as pb

BOT = "bot"


def test_session_id_is_stable_per_card():
    assert pb.session_id("42") == pb.session_id("42")
    assert pb.session_id("42") != pb.session_id("43")


def test_split_status_strips_trailers():
    reply = "Done the thing.\nATTACH: /tmp/a.png\nLABEL: Scripts\nSTATUS: review"
    assert pb.split_status(reply) == ("Done the thing.", "review", ["/tmp/a.png"], "Scripts")


def test_split_status_defaults_to_waiting():
    assert pb.split_status("no trailer")[1] == "waiting"
    assert pb.split_status("")[1] == "waiting"


def test_agent_can_never_close_a_card():
    # Done/Parked are the human's call: the bridge downgrades them.
    for status in ("done", "parked", "nonsense"):
        text, got, _, _ = pb.split_status(f"answer\nSTATUS: {status}")
        assert (text, got) == ("answer", "waiting")


def test_parse_verdict():
    assert pb.parse_verdict("Looks fine.\nVERDICT: waiting") == ("waiting", "Looks fine.")
    assert pb.parse_verdict("Tests fail.\nVERDICT: rework") == ("rework", "Tests fail.")
    assert pb.parse_verdict("all good\nVERDICT: done")[0] == "waiting"
    assert pb.parse_verdict("forgot the verdict") == ("waiting", "forgot the verdict")


def test_needs_agent():
    mine, theirs = [{"userId": BOT}], [{"userId": BOT}, {"userId": "me"}]
    assert not pb.needs_agent("draft", theirs, BOT)  # drafts are never touched
    assert not pb.needs_agent(None, theirs, BOT)  # unknown list
    assert pb.needs_agent("inbox", [], BOT)
    assert pb.needs_agent("working", mine, BOT)  # interrupted run is picked up again
    assert pb.needs_agent("waiting", theirs, BOT)  # the user replied
    assert not pb.needs_agent("waiting", mine, BOT)  # bot spoke last
    assert not pb.needs_agent("waiting", [], BOT)


def test_reply_rules_link_style():
    assert "https://kb.example/<repo path>" in pb.reply_rules("https://kb.example/")
    assert "repo-relative path" in pb.reply_rules("")


def test_step_line_truncates():
    line = pb.step_line({"name": "Bash", "input": {"command": "x" * 200}})
    assert line.startswith("- Bash: ") and len(line) == len("- Bash: ") + 90
