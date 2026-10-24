"""Thin Bedrock Converse wrapper. The model writes words and structure, never prices."""

from __future__ import annotations

import json
import os
import re
from functools import cache

import boto3


@cache
def _client():
    return boto3.client("bedrock-runtime")


def converse(
    system: str,
    text: str,
    *,
    image: bytes | None = None,
    image_format: str = "jpeg",
    model_id: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.4,
) -> str:
    content: list[dict] = []
    if image is not None:
        content.append({"image": {"format": image_format, "source": {"bytes": image}}})
    content.append({"text": text})
    resp = _client().converse(
        modelId=model_id or os.environ["TEXT_MODEL_ID"],
        system=[{"text": system}],
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return "".join(part.get("text", "") for part in resp["output"]["message"]["content"])


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_json(text: str) -> dict:
    """First JSON object in a model reply, tolerating code fences and chatter."""
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError("no JSON object in model reply")
    return json.loads(match.group(0))


def converse_json(system: str, text: str, **kwargs) -> dict:
    return parse_json(converse(system, text, temperature=0.0, **kwargs))
