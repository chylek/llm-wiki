#!/usr/bin/env bash
# List raw/ captures that haven't been distilled yet (status: unprocessed).
set -euo pipefail
cd "$(dirname "$0")/.."

matches=$(grep -rl --include='*.md' '^status: unprocessed$' raw 2>/dev/null | grep -v '/README\.md$' || true)
if [[ -z "$matches" ]]; then
    echo "inbox empty"
else
    echo "$matches"
fi
