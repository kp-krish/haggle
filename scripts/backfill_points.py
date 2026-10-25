"""Give points and achievements for pickups completed before ranks existed.

Points follow the current rules for what the user record can tell us: 50 per
completed pickup, minus cancellations and no-shows. Students who already have
points are left alone, so running it twice changes nothing.

    python scripts/backfill_points.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import game  # noqa: E402

REGION = "us-east-2"


def users_table():
    cf = boto3.client("cloudformation", region_name=REGION)
    resource = cf.describe_stack_resource(StackName="haggle-dev", LogicalResourceId="UsersTable")
    name = resource["StackResourceDetail"]["PhysicalResourceId"]
    return boto3.resource("dynamodb", region_name=REGION).Table(name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    table = users_table()
    for user in table.scan()["Items"]:
        done = int(user.get("done_count", 0))
        if "points" in user or not (done or user.get("cancel_count") or user.get("no_show_count")):
            continue
        points = (
            done * game.PICKUP_POINTS
            + int(user.get("cancel_count", 0)) * game.CANCEL_POINTS
            + int(user.get("no_show_count", 0)) * game.NO_SHOW_POINTS
        )
        achievements = {"first_deal": user.get("updated_at") or "2026-10-25"} if done else {}
        print(f"{user['user_id']}: {done} pickups -> {points} points ({game.rank(points)['name']})")
        if not args.dry_run:
            table.update_item(
                Key={"user_id": user["user_id"]},
                UpdateExpression="SET points = :p, achievements = :a",
                ExpressionAttributeValues={":p": points, ":a": achievements},
            )


if __name__ == "__main__":
    main()
