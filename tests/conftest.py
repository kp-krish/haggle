"""Fake AWS (moto) shaped like template.yaml, for tests that touch store/DynamoDB/KMS."""

import os

import boto3
import pytest
from moto import mock_aws

TABLES = {
    "users": ("user_id", None, []),
    "listings": ("listing_id", None, [("by_category", "category"), ("by_seller", "seller_id")]),
    "wants": ("want_id", None, [("by_category", "category"), ("by_buyer", "buyer_id")]),
    "deals": (
        "deal_id",
        None,
        [("by_seller", "seller_id"), ("by_buyer", "buyer_id"), ("by_listing", "listing_id")],
    ),
    "offers": ("deal_id", "round_side", []),
    "places": ("place_id", None, []),
}


def _clear_caches():
    import interactions
    import listing_agent
    import llm
    import notify
    import store

    for fn in (
        store._dynamodb,
        store._kms,
        store.discord_secret,
        interactions._lambda,
        listing_agent._s3,
        llm._client,
        notify._dm_channel,
    ):
        fn.cache_clear()


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        _clear_caches()
        ddb = boto3.client("dynamodb")
        for name, (pk, sk, indexes) in TABLES.items():
            attrs = {pk} | ({sk} if sk else set())
            if indexes:
                attrs |= {"created_at"} | {key for _, key in indexes}
            schema = [{"AttributeName": pk, "KeyType": "HASH"}]
            if sk:
                schema.append({"AttributeName": sk, "KeyType": "RANGE"})
            kwargs = {}
            if indexes:
                kwargs["GlobalSecondaryIndexes"] = [
                    {
                        "IndexName": index,
                        "KeySchema": [
                            {"AttributeName": key, "KeyType": "HASH"},
                            {"AttributeName": "created_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                    for index, key in indexes
                ]
            ddb.create_table(
                TableName=f"test-{name}",
                KeySchema=schema,
                AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in attrs],
                BillingMode="PAY_PER_REQUEST",
                **kwargs,
            )
            monkeypatch.setenv(f"{name.upper()}_TABLE", f"test-{name}")

        key_id = boto3.client("kms").create_key()["KeyMetadata"]["KeyId"]
        monkeypatch.setenv("LIMITS_KEY_ID", key_id)
        boto3.client("s3").create_bucket(
            Bucket="test-photos",
            CreateBucketConfiguration={"LocationConstraint": "us-east-2"},
        )
        monkeypatch.setenv("PHOTOS_BUCKET", "test-photos")
        monkeypatch.setenv("WORKER_FUNCTION", "test-worker")
        monkeypatch.setenv("TEXT_MODEL_ID", "test-text")
        monkeypatch.setenv("VISION_MODEL_ID", "test-vision")
        yield
    _clear_caches()


@pytest.fixture(autouse=True)
def _no_real_secret(monkeypatch):
    monkeypatch.setenv("DISCORD_SECRET_ARN", "unused")
    yield
    os.environ.pop("DISCORD_SECRET_ARN", None)
