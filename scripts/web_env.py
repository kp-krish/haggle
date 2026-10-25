"""Write web/.env.local for running the site locally, without printing any secret.

Pulls the API URL and signing secret from the deployed stack, the Discord ids from
the root .env, and generates AUTH_SECRET once. DISCORD_CLIENT_SECRET comes from .env
(Discord developer portal > OAuth2 > Client Secret).

    python scripts/web_env.py
"""

import json
import secrets
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push_secrets import ENV_PATH, read_env  # noqa: E402
from web_call import REGION, stack_outputs  # noqa: E402

TARGET = Path(__file__).resolve().parent.parent / "web" / ".env.local"


def main() -> None:
    env = read_env(ENV_PATH)
    existing = read_env(TARGET) if TARGET.exists() else {}
    out = stack_outputs()
    web = json.loads(
        boto3.client("secretsmanager", region_name=REGION)
        .get_secret_value(SecretId=out["WebSecretArn"])["SecretString"]
    )
    values = {
        "AUTH_SECRET": existing.get("AUTH_SECRET") or secrets.token_urlsafe(48),
        "AUTH_DISCORD_ID": env["DISCORD_APP_ID"],
        "AUTH_DISCORD_SECRET": env.get("DISCORD_CLIENT_SECRET", ""),
        "AUTH_TRUST_HOST": "true",
        "DISCORD_GUILD_ID": env["DISCORD_GUILD_ID"],
        "HAGGLE_API_URL": out["WebApiUrl"],
        "HAGGLE_HMAC_SECRET": web["hmac_secret"],
    }
    TARGET.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    missing = [k for k, v in values.items() if not v]
    print(f"Wrote {TARGET} ({len(values)} values)")
    if missing:
        print("Still missing:", ", ".join(missing), "- add DISCORD_CLIENT_SECRET to .env")


if __name__ == "__main__":
    main()
