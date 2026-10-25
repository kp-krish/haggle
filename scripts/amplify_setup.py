"""Create (or update) the Amplify Hosting app for the website and start a build.

Connects the GitHub repo with your `gh` login token (passed straight to AWS, never
printed), copies the site's settings from web/.env.local, and deploys the `main`
branch on every push.

    python scripts/amplify_setup.py
"""

import subprocess
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push_secrets import read_env  # noqa: E402

APP_NAME = "haggle-web"
REPO = "https://github.com/kp-krish/haggle"
BRANCH = "main"
REGION = "us-east-2"
ENV_FILE = Path(__file__).resolve().parent.parent / "web" / ".env.local"


def main() -> None:
    amplify = boto3.client("amplify", region_name=REGION)
    env = read_env(ENV_FILE)
    missing = [k for k, v in env.items() if not v]
    if missing:
        raise SystemExit(f"web/.env.local is missing: {', '.join(missing)}")
    env["AMPLIFY_MONOREPO_APP_ROOT"] = "web"

    existing = next((a for a in amplify.list_apps()["apps"] if a["name"] == APP_NAME), None)
    if existing:
        app_id = existing["appId"]
        domain = existing["defaultDomain"]
    else:
        token = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        ).stdout.strip()
        app = amplify.create_app(
            name=APP_NAME,
            description="Haggle website (Next.js)",
            repository=REPO,
            platform="WEB_COMPUTE",
            accessToken=token,
            environmentVariables=env,
            enableBranchAutoBuild=False,
        )["app"]
        app_id, domain = app["appId"], app["defaultDomain"]
        print(f"Created Amplify app {app_id}")

    site = f"https://{BRANCH}.{domain}"
    env["AUTH_URL"] = site
    amplify.update_app(appId=app_id, environmentVariables=env)

    branches = {b["branchName"] for b in amplify.list_branches(appId=app_id)["branches"]}
    if BRANCH not in branches:
        amplify.create_branch(
            appId=app_id,
            branchName=BRANCH,
            framework="Next.js - SSR",
            stage="PRODUCTION",
            enableAutoBuild=True,
        )
    job = amplify.start_job(appId=app_id, branchName=BRANCH, jobType="RELEASE")
    print(f"Build started: job {job['jobSummary']['jobId']}")
    print(f"Site: {site}")
    print(f"Discord redirect to add: {site}/api/auth/callback/discord")


if __name__ == "__main__":
    main()
