"""Copy Discord credentials from the local .env into AWS Secrets Manager.

The bot token never goes into git, CloudFormation parameters or a command line.

    python scripts/push_secrets.py [--stage dev] [--region us-east-2]
"""

import argparse
import json
from pathlib import Path

import boto3

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
FIELDS = {
    "DISCORD_APP_ID": "app_id",
    "DISCORD_PUBLIC_KEY": "public_key",
    "DISCORD_BOT_TOKEN": "bot_token",
    "DISCORD_GUILD_ID": "guild_id",
    "DISCORD_LISTINGS_CHANNEL_ID": "listings_channel_id",
}


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--region", default="us-east-2")
    args = parser.parse_args()

    env = read_env(ENV_PATH)
    missing = [k for k in FIELDS if not env.get(k)]
    if missing:
        raise SystemExit(f"missing in .env: {', '.join(missing)}")

    secret = {name: env[key] for key, name in FIELDS.items()}
    client = boto3.client("secretsmanager", region_name=args.region)
    client.put_secret_value(
        SecretId=f"haggle/{args.stage}/discord", SecretString=json.dumps(secret)
    )
    print(f"Updated haggle/{args.stage}/discord ({len(secret)} fields)")


if __name__ == "__main__":
    main()
