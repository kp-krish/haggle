"""Discord REST calls: DMs, channel posts, and edits to deferred interaction replies.

Uses only the standard library so every Lambda can import it without extra packages.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from functools import cache

import store

API = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/kp-krish/haggle, 0.1)"

# Interaction response types
PONG = 1
MESSAGE = 4
DEFERRED_MESSAGE = 5
DEFERRED_UPDATE = 6
UPDATE_MESSAGE = 7
AUTOCOMPLETE_RESULT = 8
MODAL = 9

EPHEMERAL = 1 << 6

# Button styles
PRIMARY, SECONDARY, SUCCESS, DANGER = 1, 2, 3, 4

COLOR = 0xF5A623


class DiscordError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Discord API {status}: {body[:300]}")
        self.status = status


def _request(
    method: str,
    path: str,
    payload: dict | None = None,
    files: list[tuple[str, bytes, str]] | None = None,
    auth: bool = True,
):
    headers = {"User-Agent": USER_AGENT}
    if auth:
        headers["Authorization"] = f"Bot {store.discord_secret()['bot_token']}"

    if files:
        boundary = uuid.uuid4().hex
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
            f"Content-Type: application/json\r\n\r\n{json.dumps(payload or {})}\r\n".encode()
        ]
        for i, (name, data, content_type) in enumerate(files):
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="files[{i}]"; '
                f'filename="{name}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
                + data
                + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = None

    for attempt in range(3):
        req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")
            if e.code == 429 and attempt < 2:
                time.sleep(min(float(json.loads(text).get("retry_after", 1)), 5))
                continue
            raise DiscordError(e.code, text) from None
    raise DiscordError(429, "rate limited")


# ---------- Interaction replies (no bot token needed; the interaction token is the auth)


def edit_original(app_id: str, token: str, payload: dict) -> None:
    _request("PATCH", f"/webhooks/{app_id}/{token}/messages/@original", payload, auth=False)


def followup(app_id: str, token: str, payload: dict) -> None:
    _request("POST", f"/webhooks/{app_id}/{token}", payload, auth=False)


# ---------- Bot messages


@cache
def _dm_channel(user_id: str) -> str:
    return _request("POST", "/users/@me/channels", {"recipient_id": user_id})["id"]


def dm(user_id: str, payload: dict) -> dict:
    return _request("POST", f"/channels/{_dm_channel(user_id)}/messages", payload)


def post_channel(
    channel_id: str, payload: dict, files: list[tuple[str, bytes, str]] | None = None
) -> dict:
    return _request("POST", f"/channels/{channel_id}/messages", payload, files)


def edit_message(channel_id: str, message_id: str, payload: dict) -> None:
    _request("PATCH", f"/channels/{channel_id}/messages/{message_id}", payload)


# ---------- Message building


def button(label: str, custom_id: str, style: int = PRIMARY) -> dict:
    return {"type": 2, "style": style, "label": label, "custom_id": custom_id}


def row(*buttons: dict) -> dict:
    return {"type": 1, "components": list(buttons)}


def text_input(
    custom_id: str,
    label: str,
    placeholder: str = "",
    value: str = "",
    paragraph: bool = False,
    required: bool = True,
    max_length: int = 200,
) -> dict:
    field = {
        "type": 4,
        "custom_id": custom_id,
        "label": label,
        "style": 2 if paragraph else 1,
        "required": required,
        "max_length": max_length,
    }
    if placeholder:
        field["placeholder"] = placeholder
    if value:
        field["value"] = value
    return {"type": 1, "components": [field]}


def respond(response_type: int, data: dict | None = None) -> dict:
    """API Gateway response carrying a Discord interaction response."""
    body = {"type": response_type}
    if data is not None:
        body["data"] = data
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def private(content: str, **extra) -> dict:
    """An immediate reply only the invoking student can see."""
    return respond(MESSAGE, {"content": content, "flags": EPHEMERAL, **extra})
