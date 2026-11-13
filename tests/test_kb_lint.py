"""kb_lint on a throwaway knowledge base built in a temp dir."""

import datetime as dt

import kb_lint

NOW = dt.datetime(2026, 1, 31, tzinfo=dt.timezone.utc)
KNOWLEDGE_FM = "---\ntitle: T\ntags: [x]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n"


def make(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for top in ("knowledge", "memory", "raw"):
        (root / top).mkdir(exist_ok=True)


def test_clean_kb(tmp_path):
    make(tmp_path, {
        "knowledge/a/one.md": KNOWLEDGE_FM + "see [[two]]",
        "knowledge/a/two.md": KNOWLEDGE_FM + "see [[one|label]] and `[[not-a-link]]`",
    })  # fmt: skip
    assert kb_lint.lint(tmp_path, NOW) == ([], [])


def test_errors(tmp_path):
    make(tmp_path, {
        "knowledge/a/one.md": KNOWLEDGE_FM + "[[missing]] [[a/one]]",
        "knowledge/b/one.md": "no frontmatter",
        "knowledge/a/pic.png": "",
    })  # fmt: skip
    errors, _ = kb_lint.lint(tmp_path, NOW)
    text = "\n".join(errors)
    for expected in ("duplicate slug 'one'", "broken link [[missing]]", "path-style link", "no YAML frontmatter",
                     "non-markdown file"):  # fmt: skip
        assert expected in text


def test_memory_warnings(tmp_path):
    make(tmp_path, {
        "memory/old.md": "---\ntitle: T\nstatus: in-progress\ncreated: 2025-12-01\nupdated: 2025-12-01\n---\n",
        "memory/fin.md": "---\ntitle: T\nstatus: done\ncreated: 2026-01-30\nupdated: 2026-01-30\n---\n",
    })  # fmt: skip
    errors, warnings = kb_lint.lint(tmp_path, NOW)
    assert errors == []
    assert any("not updated for 61 days" in w for w in warnings)
    assert any("status done" in w for w in warnings)
