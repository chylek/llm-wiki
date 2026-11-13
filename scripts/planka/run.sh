#!/usr/bin/env bash
# Cron entry point for the Planka bridge. Loads settings from the repo's
# .env (never committed), then runs the dispatcher under a lock so two
# overlapping cron ticks can't both dispatch.
#
#   * * * * * /path/to/llm-wiki/scripts/planka/run.sh >> ~/.local/log/llm-wiki.log 2>&1
#
# The dispatcher itself finishes in a second or two; agent runs happen in
# detached workers it starts (see planka_board.py).
set -euo pipefail
cd "$(dirname "$0")/../.."

if [[ -f .env ]]; then
    # `set -a` exports every variable the file assigns, so the Python
    # process and the `claude` CLI it starts both see them.
    set -a
    # shellcheck source=/dev/null
    source .env
    set +a
fi

# cron starts with a minimal PATH; the claude CLI usually lives in ~/.local/bin.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

# -n: give up immediately if the previous tick still holds the lock.
# -E 0: and treat that as success, so it doesn't look like a failure.
exec flock -n -E 0 "${XDG_RUNTIME_DIR:-/tmp}/llm-wiki-planka.lock" \
    python3 scripts/planka/planka_board.py
