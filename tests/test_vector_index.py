"""Chunking rules of the semantic index (no Ollama needed)."""

import pytest

pytest.importorskip("chromadb")
import vector_index as vi  # noqa: E402 - after the importorskip guard


def test_whole_note_without_headings():
    assert vi.chunk_markdown("---\ntitle: x\n---\nhello") == [("(whole)", "hello")]


def test_sections_intro_and_duplicates():
    text = "intro\n## A\none\n## B\n## A\ntwo\n```\n## not a heading\n```"
    labels = [label for label, _ in vi.chunk_markdown(text)]
    assert labels == ["(intro)", "A", "A (2)"]  # empty B dropped, fenced heading ignored
    assert "## not a heading" in vi.chunk_markdown(text)[-1][1]
