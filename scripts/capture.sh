#!/usr/bin/env bash
# Capture: drop a thought, link or paste into raw/ as-is. No judgment, no
# categorising - deciding where it belongs is the distill step's job later.
#
#   scripts/capture.sh "https://example.com/article - read the caching part"
set -euo pipefail
cd "$(dirname "$0")/.."

text="${*:-}"
if [[ -z "$text" ]]; then
    echo "usage: scripts/capture.sh <text or link to capture>" >&2
    exit 1
fi

# Timestamp first so the inbox sorts chronologically; a short slug from the
# text makes the filename recognisable.
ts=$(date +%Y-%m-%d-%H%M%S)
slug=$(printf '%s' "$text" | tr '[:upper:]' '[:lower:]' | head -c 40 | tr -c 'a-z0-9' '-' | tr -s '-' | sed 's/^-//;s/-$//')
file="raw/${ts}-${slug:-capture}.md"

cat > "$file" <<NOTE
---
created: $(date -Iseconds)
status: unprocessed
distilled_into: []
---

$text
NOTE

echo "captured -> $file"
