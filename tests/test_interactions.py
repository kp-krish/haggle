import json
from unittest import mock

import pytest
from nacl.signing import SigningKey

import interactions

KEY = SigningKey.generate()
PUBLIC = KEY.verify_key.encode().hex()


def signed_event(payload: dict, key: SigningKey = KEY, timestamp: str = "1700000000") -> dict:
    body = json.dumps(payload)
    signature = key.sign(f"{timestamp}{body}".encode()).signature.hex()
    return {
        "headers": {"X-Signature-Ed25519": signature, "X-Signature-Timestamp": timestamp},
        "body": body,
        "isBase64Encoded": False,
    }


@pytest.fixture(autouse=True)
def secret():
    with mock.patch("store.discord_secret", return_value={"public_key": PUBLIC}):
        yield


def test_ping_gets_pong():
    resp = interactions.handler(signed_event({"type": 1}), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"type": 1}


def test_wrong_key_is_rejected():
    resp = interactions.handler(signed_event({"type": 1}, key=SigningKey.generate()), None)
    assert resp["statusCode"] == 401


def test_tampered_body_is_rejected():
    event = signed_event({"type": 1})
    event["body"] = event["body"].replace("1", "2")
    assert interactions.handler(event, None)["statusCode"] == 401


def test_missing_headers_are_rejected():
    assert interactions.handler({"headers": {}, "body": "{}"}, None)["statusCode"] == 401
