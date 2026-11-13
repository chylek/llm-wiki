---
name: capture
description: Quickly file a thought, link, or paste into the raw/ inbox without deciding where it belongs yet. Use when the user says "capture this", "note this down", "add to inbox", or pastes something to save for later.
---

Run `scripts/capture.sh "<text>"` with the given content, quoted verbatim.

Don't summarize, categorize, or ask about tags or folders: that is the
`distill` skill's job, later, with more context. Capture has to be fast and
frictionless or it won't be used.

Capture long pastes and links as-is rather than condensing them.

Confirm with the single line the script prints (`captured -> raw/...`),
nothing else.
