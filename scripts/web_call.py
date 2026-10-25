"""Call the deployed website API as a given Discord user (signs like the Next.js server).

    python scripts/web_call.py GET /web/listings --user 1234 [--query "q=lamp"] [--body '{}']
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from web_api import sign  # noqa: E402

STACK, REGION = "haggle-dev", "us-east-2"


def stack_outputs() -> dict[str, str]:
    cf = boto3.client("cloudformation", region_name=REGION)
    outputs = cf.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("method")
    parser.add_argument("path")
    parser.add_argument("--user", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--body", default=None)
    args = parser.parse_args()

    out = stack_outputs()
    secrets = boto3.client("secretsmanager", region_name=REGION)
    secret = json.loads(secrets.get_secret_value(SecretId=out["WebSecretArn"])["SecretString"])
    body = args.body.encode() if args.body else b""
    ts = str(int(time.time()))
    signature = sign(
        secret["hmac_secret"].encode(), ts, args.method, args.path, args.query, args.user, body
    )
    url = out["WebApiUrl"] + args.path + (f"?{args.query}" if args.query else "")
    req = urllib.request.Request(
        url,
        data=body or None,
        method=args.method,
        headers={
            "X-Haggle-User": args.user,
            "X-Haggle-Timestamp": ts,
            "X-Haggle-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(resp.status, json.dumps(json.loads(resp.read()), indent=2)[:3000])
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode()[:500])


if __name__ == "__main__":
    main()
