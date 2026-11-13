#!/usr/bin/env python3
"""One-time setup of a Planka board for the agent bridge.

Creates, as the Planka admin:

1. a private project and a board with the lists ``planka_board.py`` expects
   (Draft, Inbox, Working, Review, Waiting on you, Done, Parked),
2. a dedicated bot user (role *board user*, editor on that board only), with
   the terms of service accepted so it can use the API,
3. an API key for the bot.

and prints the ``.env`` lines for the bridge. Run it once against a fresh
Planka; it does not try to reconcile an existing board.

usage:
    PLANKA_URL=http://localhost:3000 scripts/planka/setup_board.py [--admin admin] [--bot agent]

The admin password is read from ``PLANKA_ADMIN_PASSWORD`` or prompted for;
it is never stored. The bot's password is random and printed once - you only
need it to log in as the bot by hand. Stdlib only.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from typing import Any

from planka_board import LISTS

#: Lists in board order: the bridge's lists plus the two only the human uses.
BOARD_LISTS = [*LISTS.values(), "Done", "Parked"]


def call(base: str, method: str, path: str, body: dict[str, Any] | None = None, token: str = "") -> Any:
    """JSON request; HTTP errors are returned as their decoded body plus ``_status``."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base}/api{path}", method=method, data=json.dumps(body).encode() if body else None, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        payload = json.loads(err.read() or b"{}")
        payload["_status"] = err.code
        return payload


def login(base: str, username: str, password: str) -> str:
    """Access token for a user, accepting the terms of service on first login.

    Planka 2.x refuses the first login of every user until the terms are
    accepted; the refusal carries a ``pendingToken`` to accept them with.
    """
    res = call(base, "POST", "/access-tokens", {"emailOrUsername": username, "password": password})
    if "item" in res:
        return res["item"]
    if "pendingToken" not in res:
        sys.exit(f"login as {username} failed: {res}")
    terms = call(base, "GET", "/terms?type=general&language=en-US")
    accepted = call(
        base,
        "POST",
        "/access-tokens/accept-terms",
        {"pendingToken": res["pendingToken"], "signature": terms["item"]["signature"]},
    )
    if "item" not in accepted:
        sys.exit(f"accepting terms for {username} failed: {accepted}")
    return accepted["item"]


def must(res: Any, what: str) -> dict[str, Any]:
    """The created ``item`` of an API response, or exit with the error."""
    if "item" not in res:
        sys.exit(f"{what} failed: {res}")
    return res["item"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--admin", default="admin", help="admin username (default: admin)")
    ap.add_argument("--bot", default="agent", help="bot username to create (default: agent)")
    ap.add_argument("--project", default="LLM Wiki")
    ap.add_argument("--board", default="Tasks")
    args = ap.parse_args()

    base = os.environ.get("PLANKA_URL", "http://localhost:3000").rstrip("/")
    admin_pw = os.environ.get("PLANKA_ADMIN_PASSWORD") or getpass.getpass(f"Planka password for {args.admin}: ")
    admin = login(base, args.admin, admin_pw)

    project = must(call(base, "POST", "/projects", {"type": "private", "name": args.project}, admin), "project")
    board = must(
        call(base, "POST", f"/projects/{project['id']}/boards", {"name": args.board, "position": 65536}, admin),
        "board",
    )
    for i, name in enumerate(BOARD_LISTS, start=1):
        body = {"type": "active", "name": name, "position": 65536 * i}
        must(call(base, "POST", f"/boards/{board['id']}/lists", body, admin), f"list {name}")

    bot_pw = secrets.token_urlsafe(18)
    bot = must(
        call(
            base,
            "POST",
            "/users",
            {
                "email": f"{args.bot}@example.invalid",  # never mailed; Planka just requires one
                "password": bot_pw,
                "name": "Agent",
                "username": args.bot,
                "role": "boardUser",
            },
            admin,
        ),
        "bot user",
    )
    login(base, args.bot, bot_pw)  # accepts the terms for the bot
    must(
        call(base, "POST", f"/boards/{board['id']}/board-memberships", {"userId": bot["id"], "role": "editor"}, admin),
        "board membership",
    )
    key = call(base, "POST", f"/users/{bot['id']}/api-key", None, admin)
    if "included" not in key:
        sys.exit(f"API key creation failed: {key}")

    print(f"# bot user {args.bot!r}, password (only needed for a manual login): {bot_pw}", file=sys.stderr)
    print(f"PLANKA_URL={base}")
    print(f"PLANKA_BOARD_ID={board['id']}")
    print(f"PLANKA_API_KEY={key['included']['apiKey']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
