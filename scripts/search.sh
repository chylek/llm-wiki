#!/usr/bin/env bash
# Search knowledge/, memory/ and raw/ in three layers:
#
#   1. lexical   - files containing the term, or tagging it in frontmatter
#   2. graph     - notes one [[wikilink]] hop away from a lexical hit
#   3. semantic  - notes whose *meaning* is close (local embeddings),
#                  even with no shared words at all
#
# Layer 3 is best-effort: if the venv, Ollama or the index is missing it is
# silently skipped, so search never breaks because a service is down.
#
#   scripts/search.sh caching
set -euo pipefail
cd "$(dirname "$0")/.."

term="${1:-}"
if [[ -z "$term" ]]; then
    echo "usage: scripts/search.sh <term>" >&2
    exit 1
fi

# --- 1. lexical ------------------------------------------------------------
content_hits=$(grep -rli --include='*.md' -F -- "$term" knowledge memory raw 2>/dev/null || true)
# Escape regex metacharacters: the term is text, not a pattern.
# shellcheck disable=SC2016 # the $ is a literal inside the sed bracket expression
term_re=$(printf '%s' "$term" | sed 's/[][\.*^$(){}?+|/]/\\&/g')
tag_hits=$(grep -rli --include='*.md' -E "^tags:.*$term_re" knowledge memory raw 2>/dev/null || true)
all_hits=$(printf '%s\n%s\n' "$content_hits" "$tag_hits" | sed '/^$/d' | sort -u)

# --- 2. graph: one hop of [[wikilinks]] out of every direct hit -------------
related=""
if [[ -n "$all_hits" ]]; then
    linked=$(while IFS= read -r f; do
        grep -o '\[\[[^]]*\]\]' "$f" 2>/dev/null | tr -d '[]' | cut -d'|' -f1 | cut -d'#' -f1 || true
    done <<< "$all_hits" | sort -u)
    while IFS= read -r slug; do
        [[ -z "$slug" ]] && continue
        path=$(find knowledge memory -name "${slug}.md" -print -quit)
        if [[ -n "$path" ]] && ! grep -qxF "$path" <<< "$all_hits"; then
            related+="$path"$'\n'
        fi
    done <<< "$linked"
fi

# --- 3. semantic (runs even without lexical hits - that's its whole point) --
semantic=""
if [[ -x .venv/bin/python3 ]]; then
    # Capture the exit code instead of letting `set -e` abort the search.
    semantic="$(.venv/bin/python3 scripts/vector_index.py query -- "$term" 5 2>/dev/null)" || semantic=""
fi

if [[ -z "$all_hits" && -z "$semantic" ]]; then
    echo "no matches for: $term"
    exit 0
fi
if [[ -n "$all_hits" ]]; then
    while IFS= read -r f; do
        echo "== $f =="
        grep -n -i -F -- "$term" "$f" | head -3 || true
        echo
    done <<< "$all_hits"
fi
if [[ -n "$related" ]]; then
    echo "-- related via [[wikilinks]] (not direct matches on '$term') --"
    printf '%s' "$related" | sed '/^$/d' | sort -u
fi
if [[ -n "$semantic" ]]; then
    echo
    echo "-- related via semantic similarity (no exact match needed) --"
    printf '%s\n' "$semantic"
fi
