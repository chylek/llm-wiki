#!/usr/bin/env bash
# Scaffold a new atomic note at knowledge/<topic>/<slug>.md with frontmatter.
#
#   scripts/new-note.sh concepts/prompt-caching llm,cost
#
# Slugs must be unique across *all* topic folders, because [[wikilinks]]
# resolve by slug alone - that's what lets a note move between folders
# without breaking links.
set -euo pipefail
cd "$(dirname "$0")/.."

path="${1:-}"
tags="${2:-}"
topic="${path%%/*}"
slug="${path#*/}"
if [[ -z "$path" || "$topic" == "$path" || "$slug" == */* ]]; then
    echo "usage: scripts/new-note.sh <topic>/<slug> [tag1,tag2]" >&2
    echo "topics: $(find knowledge -mindepth 1 -maxdepth 1 -type d -printf '%f ')" >&2
    exit 1
fi
if [[ ! "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "slug must be lowercase-kebab-case: $slug" >&2
    exit 1
fi
if [[ ! -d "knowledge/$topic" ]]; then
    echo "no such topic: $topic (mkdir knowledge/$topic first if it's genuinely new)" >&2
    exit 1
fi
existing=$(find knowledge -name "${slug}.md" -print -quit)
if [[ -n "$existing" ]]; then
    echo "already exists: $existing" >&2
    exit 1
fi

file="knowledge/${topic}/${slug}.md"
title=$(printf '%s' "$slug" | tr '-' ' ' | sed 's/\b\(.\)/\u\1/g')
now=$(date -Iseconds)
cat > "$file" <<NOTE
---
title: $title
tags: [$tags]
created: $now
updated: $now
---

# $title

NOTE
echo "created -> $file"
