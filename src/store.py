"""DynamoDB, KMS and Secrets Manager helpers shared by the Lambdas.

Private limits (floor / ceiling) are encrypted one field at a time with an encryption
context naming the record and its owner, so a ciphertext copied onto another record or
decrypted for the wrong owner fails.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import UTC, datetime
from functools import cache

import boto3

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


@cache
def _dynamodb():
    return boto3.resource("dynamodb")


@cache
def _kms():
    return boto3.client("kms")


def table(name: str):
    """``table("listings")`` -> the Listings table, from the LISTINGS_TABLE env var."""
    return _dynamodb().Table(os.environ[f"{name.upper()}_TABLE"])


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    """Time-sortable id like ``lst_01JB3...``: 48-bit ms timestamp + 80 random bits."""
    value = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    chars = []
    for _ in range(26):
        value, rem = divmod(value, 32)
        chars.append(_CROCKFORD[rem])
    return f"{prefix}_{''.join(reversed(chars))}"


def _context(record: str, owner_id: str) -> dict[str, str]:
    return {"purpose": "price-limit", "record": record, "owner": owner_id}


def encrypt_limit(amount: int, record: str, owner_id: str) -> bytes:
    """Encrypt a private limit. ``record`` is e.g. ``"listing#lst_..."``."""
    resp = _kms().encrypt(
        KeyId=os.environ["LIMITS_KEY_ID"],
        Plaintext=str(int(amount)).encode(),
        EncryptionContext=_context(record, owner_id),
    )
    return resp["CiphertextBlob"]


def decrypt_limit(ciphertext: bytes, record: str, owner_id: str) -> int:
    """Decrypt a private limit. Only negotiator roles are allowed kms:Decrypt."""
    resp = _kms().decrypt(
        CiphertextBlob=bytes(ciphertext),
        EncryptionContext=_context(record, owner_id),
    )
    return int(resp["Plaintext"].decode())


def conditional_failed() -> type[Exception]:
    """The exception DynamoDB raises when a ConditionExpression is not met."""
    return _dynamodb().meta.client.exceptions.ConditionalCheckFailedException


@cache
def discord_secret() -> dict[str, str]:
    """``{"app_id", "public_key", "bot_token", "guild_id", "listings_channel_id"}``."""
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=os.environ["DISCORD_SECRET_ARN"])
    return json.loads(resp["SecretString"])
