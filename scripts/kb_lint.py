#!/usr/bin/env python3
"""Lint the knowledge base: links, frontmatter, file placement, memory hygiene.

Errors break the repo's own conventions (broken/path-style [[links]], missing
frontmatter, non-markdown files in note folders, duplicate slugs, unexpected
tracked files in the repo root) and make the exit code 1 - the pre-commit
hook blocks on them. Warnings are housekeeping (done or stale memory files,
orphan notes, oversized notes, old unprocessed raw captures) and never fail.

Stdlib only and run with the system python3 on purpose: the tool that detects
breakage must not depend on the virtualenv that semantic search needs, or a
broken .venv would also silence the linter.

usage: scripts/kb_lint.py [--errors-only] [--root DIR]
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

FENCE_RE = re.compile(r"(?ms)^(```|~~~).*?^\1")
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"\[\[([^\]\n]+?)\]\]")

REQUIRED = {
    "knowledge": ("title", "tags", "created", "updated"),
    "memory": ("title", "status", "created", "updated"),
    "raw": ("created", "status"),
}
# Top-level entries a commit may contain; anything else is probably a stray
# file that belongs in artifacts/.
ROOT_ALLOWED = {
    ".claude",
    ".github",
    ".gitignore",
    ".gitleaksignore",
    ".env.example",
    "CLAUDE.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "artifacts",
    "deploy",
    "docs",
    "knowledge",
    "memory",
    "raw",
    "scripts",
    "tests",
}
RAW_BINARY_DIRS = {"originals", "images"}  # raw/<capture>/originals|images may hold binaries
MEMORY_STALE_DAYS = 21  # a task file untouched this long probably describes old reality
RAW_STALE_DAYS = 14
NOTE_MAX_LINES = 300


def strip_code(text: str) -> str:
    """Remove fenced blocks and inline code, so `[[example]]` in code isn't a link."""
    return CODE_SPAN_RE.sub("", FENCE_RE.sub("", text))


def links_in(text: str) -> list[str]:
    """Wikilink targets in a note: [[slug]], [[slug|label]] and [[slug#heading]] -> slug."""
    return [m.split("|")[0].split("#")[0].strip() for m in LINK_RE.findall(strip_code(text))]


def frontmatter(text: str) -> dict[str, str] | None:
    """Flat YAML frontmatter as a dict (top-level `key: value` lines only), or None.

    A deliberately tiny parser instead of PyYAML: the conventions only need
    top-level scalar keys, and staying stdlib-only keeps the linter unbreakable.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, val = line.split(":", 1)
            fm[key.strip()] = re.split(r"\s#", val)[0].strip()  # "C# tips" keeps its "#"
    return fm


def parse_ts(value: str) -> dt.datetime | None:
    """ISO-8601 timestamp -> aware datetime (naive ones are taken as UTC)."""
    try:
        ts = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))  # 3.10 rejects "Z"
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)


def git_lines(root: Path, *args: str) -> list[str]:
    """Output lines of a git command, or [] outside a git checkout."""
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in out.stdout.splitlines() if line]


def note_files(root: Path, top: str) -> list[Path]:
    """Markdown notes under one top-level folder (README files are docs, not notes)."""
    if top == "memory":
        return sorted(p for p in (root / "memory").glob("*.md") if p.name != "README.md")
    if top == "raw":
        return sorted(p for p in (root / "raw").rglob("*.md") if p.name not in ("README.md", "index.md"))
    return sorted(p for p in (root / top).rglob("*.md") if p.name != "README.md")


def lint(root: Path, now: dt.datetime | None = None) -> tuple[list[str], list[str]]:
    """Check the whole knowledge base under `root` -> (errors, warnings)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    errors: list[str] = []
    warnings: list[str] = []

    def rel(p: Path) -> str:
        return str(p.relative_to(root))

    # Slugs that [[links]] may resolve to: knowledge notes and memory files.
    slugs: dict[str, Path] = {}
    for top in ("knowledge", "memory"):
        for p in note_files(root, top):
            if p.stem in slugs:
                errors.append(f"duplicate slug '{p.stem}': {rel(slugs[p.stem])} and {rel(p)}")
            slugs[p.stem] = p

    inbound: dict[str, int] = {s: 0 for s in slugs}
    for top in ("knowledge", "memory", "raw"):
        for p in note_files(root, top):
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = frontmatter(text)
            if fm is None:
                errors.append(f"{rel(p)}: no YAML frontmatter")
                fm = {}
            else:
                missing = [k for k in REQUIRED[top] if not fm.get(k)]
                if missing:
                    errors.append(f"{rel(p)}: frontmatter missing {', '.join(missing)}")

            for target in links_in(text):
                if "/" in target:
                    errors.append(f"{rel(p)}: path-style link [[{target}]] - use the bare slug")
                elif target not in slugs:
                    errors.append(f"{rel(p)}: broken link [[{target}]]")
                elif target != p.stem:
                    inbound[target] += 1

            updated = parse_ts(fm.get("updated", "") or fm.get("created", ""))
            age = (now - updated).days if updated else None
            if top == "memory":
                if fm.get("status") == "done":
                    warnings.append(f"{rel(p)}: status done - distill into knowledge/ or delete")
                elif age is not None and age > MEMORY_STALE_DAYS:
                    warnings.append(f"{rel(p)}: not updated for {age} days - re-verify against reality")
            elif top == "raw":
                if fm.get("status") == "unprocessed" and age is not None and age > RAW_STALE_DAYS:
                    warnings.append(f"{rel(p)}: unprocessed for {age} days")
            elif top == "knowledge":
                lines = text.count("\n")
                if lines > NOTE_MAX_LINES:
                    warnings.append(f"{rel(p)}: {lines} lines - probably more than one idea")

    for slug, n in sorted(inbound.items()):
        if n == 0 and slugs[slug].is_relative_to(root / "knowledge"):
            warnings.append(f"{rel(slugs[slug])}: orphan (no note links to it)")

    for top in ("knowledge", "memory"):
        for p in sorted((root / top).rglob("*")):
            if p.is_file() and p.suffix != ".md":
                errors.append(f"{rel(p)}: non-markdown file in {top}/ - move it to artifacts/<slug>/")
    for p in sorted((root / "raw").rglob("*")):
        if p.is_file() and p.suffix != ".md" and not RAW_BINARY_DIRS & set(p.relative_to(root / "raw").parts):
            errors.append(f"{rel(p)}: non-markdown file in raw/ outside originals/ or images/")

    tracked_top = {line.split("/")[0] for line in git_lines(root, "ls-files")}
    for name in sorted(tracked_top - ROOT_ALLOWED):
        errors.append(f"{name}: unexpected tracked entry in repo root - see artifacts/README.md")
    untracked_top = {line.split("/")[0] for line in git_lines(root, "ls-files", "--others", "--exclude-standard")}
    for name in sorted(untracked_top - ROOT_ALLOWED):
        warnings.append(f"{name}: untracked in repo root - commit it to artifacts/ or move it out")

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--errors-only", action="store_true", help="don't print warnings")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()

    errors, warnings = lint(args.root)
    for e in errors:
        print(f"ERROR {e}")
    if not args.errors_only:
        for w in warnings:
            print(f"warn  {w}")
    if not errors and (args.errors_only or not warnings):
        print("kb-lint: clean")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
