# knowledge/

Distilled, atomic, evergreen notes: one idea per file, in your own words,
linked to related notes with `[[slug]]`.

## Topics

One level of broad folders, never deeper. Folders are for browsing;
cross-cutting organisation comes from `tags` and links.

| Folder | What goes there |
|---|---|
| `concepts/` | the ideas this repository is built on (start with [[llm-wiki-pattern]]) |

Add your own topic folders (`homelab/`, `research/`, `career/` ...) with
`mkdir knowledge/<topic>` and list them here.

## Conventions

- File name = slug, lowercase-kebab-case, **unique across all folders**:
  `[[slug]]` resolves by name alone, so notes can move between folders.
- Frontmatter: `title`, `tags`, `created`, `updated` (ISO 8601). Bump
  `updated` whenever the content changes; a note is never "finished".
- Under ~300 lines. Longer usually means two ideas: split it.
- `scripts/kb_lint.py` enforces the mechanical parts.
