"""Discord interactions endpoint: verify the Ed25519 signature, then route.

Discord sends every slash command, button click and form submit here as an HTTPS POST.
"""

from __future__ import annotations

import base64
import json

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import store

PING = 1
PONG = 1
CHANNEL_MESSAGE = 4
EPHEMERAL = 1 << 6


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def verify(public_key: str, signature: str, timestamp: str, body: str) -> bool:
    try:
        VerifyKey(bytes.fromhex(public_key)).verify(
            f"{timestamp}{body}".encode(), bytes.fromhex(signature)
        )
        return True
    except (BadSignatureError, ValueError):
        return False


def handler(event: dict, context) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()

    if not verify(
        store.discord_secret()["public_key"],
        headers.get("x-signature-ed25519", ""),
        headers.get("x-signature-timestamp", ""),
        body,
    ):
        return _response(401, {"error": "invalid request signature"})

    interaction = json.loads(body)
    if interaction["type"] == PING:
        return _response(200, {"type": PONG})

    return _response(
        200,
        {
            "type": CHANNEL_MESSAGE,
            "data": {"content": "Haggle is warming up. Commands arrive soon.", "flags": EPHEMERAL},
        },
    )
