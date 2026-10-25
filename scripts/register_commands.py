"""Register Haggle's slash commands with Discord.

Registers on the test server from .env (instant). Pass --global to register for every
server the bot is in (can take up to an hour to show up).

    python scripts/register_commands.py [--global]
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push_secrets import ENV_PATH, read_env  # noqa: E402

STRING, INTEGER, ATTACHMENT = 3, 4, 11
AREA_CHOICES = [{"name": a.title(), "value": a} for a in ("north", "central", "south")] + [
    {"name": "Any (no preference)", "value": "any"}
]

COMMANDS = [
    {
        "name": "sell",
        "description": "List an item. Your agent writes the listing and haggles for you.",
        "options": [
            {
                "type": ATTACHMENT,
                "name": "photo",
                "description": "A photo of the item",
                "required": True,
            },
            {
                "type": STRING,
                "name": "description",
                "description": "A few words: what it is, condition",
                "required": True,
                "max_length": 300,
            },
            {
                "type": INTEGER,
                "name": "asking",
                "description": "Asking price in dollars (public)",
                "required": True,
                "min_value": 1,
                "max_value": 10000,
            },
            {
                "type": STRING,
                "name": "area",
                "description": "Your part of campus, for picking a meeting spot",
                "required": True,
                "choices": AREA_CHOICES,
            },
        ],
    },
    {
        "name": "want",
        "description": "Tell your agent what you're looking for.",
        "options": [
            {
                "type": STRING,
                "name": "item",
                "description": "What you want, e.g. mini fridge",
                "required": True,
                "max_length": 100,
            },
            {
                "type": STRING,
                "name": "area",
                "description": "Your part of campus, for picking a meeting spot",
                "required": True,
                "choices": AREA_CHOICES,
            },
        ],
    },
    {"name": "deals", "description": "Your open listings, wants and negotiations."},
    {
        "name": "stop",
        "description": "Stop a listing, a want or a negotiation.",
        "options": [
            {
                "type": STRING,
                "name": "deal",
                "description": "Which one (start typing)",
                "required": True,
                "autocomplete": True,
            }
        ],
    },
    {
        "name": "cancel",
        "description": "Cancel a confirmed pickup. The other student is told right away.",
        "options": [
            {
                "type": STRING,
                "name": "booking",
                "description": "Which pickup (start typing)",
                "required": True,
                "autocomplete": True,
            }
        ],
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global", dest="is_global", action="store_true")
    args = parser.parse_args()

    env = read_env(ENV_PATH)
    app_id = env["DISCORD_APP_ID"]
    path = f"/applications/{app_id}/commands"
    if not args.is_global:
        path = f"/applications/{app_id}/guilds/{env['DISCORD_GUILD_ID']}/commands"

    req = urllib.request.Request(
        f"https://discord.com/api/v10{path}",
        data=json.dumps(COMMANDS).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bot {env['DISCORD_BOT_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/kp-krish/haggle, 0.1)",
        },
    )
    with urllib.request.urlopen(req) as resp:
        registered = json.loads(resp.read())
    print("Registered:", ", ".join(f"/{c['name']}" for c in registered))


if __name__ == "__main__":
    main()
