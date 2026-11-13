#!/usr/bin/env bash
# Look up credentials in .env without putting them in the agent's transcript.
#
#   scripts/secrets.sh            list the keys and their descriptions; values
#                                 are only shown as set/EMPTY, never printed
#   scripts/secrets.sh KEY        print one value, meant for command substitution:
#       curl -H "X-Api-Key: $(scripts/secrets.sh PLANKA_API_KEY)" ...
#
# Why: everything a command prints goes into the model's context (and to the
# model provider). Listing names lets the agent find out *which* credential
# exists and what it is for; using the value inside $(...) hands it straight
# to the command without it ever appearing in the output. A description is
# the `# comment` line directly above a key in .env.
#
# SECRETS_FILE overrides the file (used by the tests).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
file="${SECRETS_FILE:-.env}"
[[ -f "$file" ]] || { echo "no $file (copy .env.example)" >&2; exit 1; }

if [[ $# -eq 1 ]]; then
    # Last assignment wins, as when the file is sourced.
    value=$(grep -E "^$1=" "$file" | tail -1 | cut -d= -f2-) || true
    [[ -n "$value" ]] || { echo "$1 is not set in $file" >&2; exit 1; }
    printf '%s\n' "$value"
    exit 0
fi

awk -F= '
/^#/ { desc = substr($0, 3); next }
/^[[:space:]]*$/ { desc = ""; next }
/^[A-Za-z_][A-Za-z0-9_]*=/ {
    printf "%-26s %-6s %s\n", $1, ($2 == "" ? "EMPTY" : "set"), desc
    desc = ""
}' "$file"
