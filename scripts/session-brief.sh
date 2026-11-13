#!/usr/bin/env bash
# SessionStart hook (wired in .claude/settings.json). Whatever this prints is
# added to the agent's context at the start of every session: active tasks
# and their age, lint problems, and the raw/ inbox. It's how a fresh session
# "remembers" where things stand without reading the whole repo.
#
# Must be fast and must never fail the session start, hence no `set -e`.
cd "$(dirname "$0")/.." || exit 0
now=$(date +%s)
echo "## Knowledge base brief ($(date +%F))"

active=""
for f in memory/*.md; do
    [[ -e "$f" && "$(basename "$f")" != README.md ]] || continue
    status=$(sed -n 's/^status: *//p' "$f" | head -1 | cut -d' ' -f1)
    [[ "$status" == "done" ]] && continue
    updated=$(sed -n 's/^updated: *//p' "$f" | head -1)
    days=$(( (now - $(date -d "$updated" +%s 2>/dev/null || echo "$now")) / 86400 ))
    active+="- $f ($status, updated ${days}d ago)"$'\n'
done
# shellcheck disable=SC2016 # literal backticks, not a command substitution
[[ -n "$active" ]] && printf 'Active memory files (check `updated` before trusting):\n%s' "$active"

lint=$(python3 scripts/kb_lint.py 2>&1)
echo "kb-lint: $(grep -c '^ERROR' <<< "$lint") error(s), $(grep -c '^warn' <<< "$lint") warning(s) - python3 scripts/kb_lint.py"
grep -E '^(ERROR|warn  memory/)' <<< "$lint" | head -10

inbox=$(scripts/inbox.sh | grep -vc '^inbox empty$')
[[ "$inbox" -gt 0 ]] && echo "raw/ inbox: $inbox unprocessed capture(s) - distill skill"
exit 0
