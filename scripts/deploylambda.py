"""Deploy the API archive to AWS Lambda and expose it on a Function URL.

The demo tier, and only the demo tier. It is a deliberate list of what this does
*not* create, because each absence is what keeps the deployment inside the
always-free allowance rather than the twelve-month one:

* **No VPC.** The function reaches nothing private, so it needs no subnets and
  no NAT gateway — the single most expensive thing an idle AWS account can own.
* **No API Gateway.** A Function URL is HTTPS on its own and is not billed
  separately.
* **No ECR.** A zip archive, not a container image, so no registry storage.
* **No RDS.** State lives in DynamoDB instead, whose free allowance does not
  expire — RDS's dies after twelve months, at which point the deployment either
  starts costing money or starts claiming a durability it no longer has.

State now survives a cold start, so health reports `ok` rather than `degraded`.
It still must not be pointed at anything real: `PASHU_DRY_RUN` stays true and
the environment is not listed in `PASHU_LIVE_ENVIRONMENTS`, so both execution
gates are shut — see docs/SECURITY.md, control 1.

Usage:  python scripts/deploylambda.py --role <arn> [--cors https://example.com]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FUNCTION = "pashupatastra-api"
RUNTIME = "python3.13"
HANDLER = "app.handler.handler"
REGION = "us-east-1"

MEMORY_MB = 512
"""Lambda bills memory × duration, and a larger size gets proportionally more
CPU. 512 MB imports the app noticeably faster than 256 MB for the same cost per
request, because the extra CPU shortens the cold start it is billed for."""

TIMEOUT_SECONDS = 30


def aws(*args: str, region: str = REGION) -> str:
    result = subprocess.run(
        ["aws", *args, "--region", region, "--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"aws {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def exists(function: str, region: str) -> bool:
    try:
        aws("lambda", "get-function", "--function-name", function, region=region)
        return True
    except RuntimeError:
        return False


def environment(cors: list[str]) -> str:
    return json.dumps(
        {
            "Variables": {
                "PASHU_ENVIRONMENT": "dev",
                # Both execution gates shut. Neither is enough on its own.
                "PASHU_DRY_RUN": "true",
                "PASHU_LIVE_ENVIRONMENTS": "[]",
                # Empty rather than absent: `connect` treats an empty URL as
                # "no database configured" and falls back immediately, instead
                # of spending the connect timeout on every request.
                "PASHU_DATABASE_URL": "",
                # The durable store. With this set, `backend.durable()` chooses
                # DynamoDB and never dials Postgres at all.
                "PASHU_DYNAMO_TABLE": "pashupatastra",
                # Which slice of that table is the deployed console's. One table
                # holds every environment because DynamoDB's free allowance is
                # per account, so a second table would take capacity from this
                # one rather than add any. Stated explicitly here even though it
                # matches the default: this is the value that keeps a local run
                # out of the deployed data, and it should be readable at the
                # place the deployment is configured.
                "PASHU_DYNAMO_NAMESPACE": "prod",
                "PASHU_DEMO_SEED": "true",
                # The site is a blue-team console, so it is offered blue-team
                # actions. A filter on the view, not a second registry — every
                # action stays resolvable so a plan's rollback cannot vanish.
                "PASHU_ACTION_DOMAIN": "security",
                # The model, and the key that reaches it. Both come from this
                # machine's environment and neither is written down here: a key
                # in a tracked file is a key in the history, and history is
                # forever even after the file is fixed.
                **_model_env(),
                "PASHU_CORS_ORIGINS": json.dumps(cors),
            }
        }
    )


def _model_env() -> dict[str, str]:
    """Model settings for the deployed function, read from this environment.

    Defaults to the deterministic stub. A deploy that forgets the key ships a
    console whose chat says it is not configured, which is the honest failure —
    the alternative default would be a chat that invents answers.
    """
    key = os.environ.get("PASHU_MODEL_API_KEY", "")
    if not key:
        return {"PASHU_MODEL_PROVIDER": "echo"}

    env = {
        "PASHU_MODEL_PROVIDER": os.environ.get("PASHU_MODEL_PROVIDER", "openai-compat"),
        "PASHU_MODEL_ID": os.environ.get("PASHU_MODEL_ID", "openai/gpt-oss-20b"),
        "PASHU_MODEL_API_KEY": key,
    }
    # Set once Ollama is up on the always-free box. Until then there is one
    # provider, and a rate limit is a rate limit rather than a slower answer.
    fallback = os.environ.get("PASHU_FALLBACK_BASE_URL")
    if fallback:
        env["PASHU_MODEL_PROVIDER"] = "failover"
        env["PASHU_FALLBACK_BASE_URL"] = fallback
        env["PASHU_FALLBACK_MODEL"] = os.environ.get("PASHU_FALLBACK_MODEL", "qwen2.5:7b")
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, help="execution role ARN")
    parser.add_argument("--zip", default=str(ROOT / "dist" / "api.zip"))
    parser.add_argument("--function", default=FUNCTION)
    parser.add_argument("--region", default=REGION)
    parser.add_argument(
        "--cors",
        action="append",
        required=True,
        help="allowed browser origin; repeatable. The dashboard's origin must be listed.",
    )
    args = parser.parse_args()

    archive = f"fileb://{Path(args.zip).resolve()}"
    origins = args.cors
    if "*" in origins:
        # docs/DEPLOYMENT.md: the API is a public-internet endpoint and
        # `cors_origins` is set per environment. A wildcard is never
        # acceptable, including on the demo tier — it is the deployment most
        # likely to be copied as a starting point.
        parser.error("a CORS wildcard is not an acceptable origin; name the dashboard's origin")

    if exists(args.function, args.region):
        aws("lambda", "update-function-code",
            "--function-name", args.function, "--zip-file", archive, region=args.region)
        aws("lambda", "wait", "function-updated", "--function-name", args.function,
            region=args.region)
        aws("lambda", "update-function-configuration",
            "--function-name", args.function,
            "--environment", environment(origins),
            "--memory-size", str(MEMORY_MB),
            "--timeout", str(TIMEOUT_SECONDS),
            region=args.region)
    else:
        aws("lambda", "create-function",
            "--function-name", args.function,
            "--runtime", RUNTIME,
            "--role", args.role,
            "--handler", HANDLER,
            "--zip-file", archive,
            "--environment", environment(origins),
            "--memory-size", str(MEMORY_MB),
            "--timeout", str(TIMEOUT_SECONDS),
            "--tags", "Project=pashupatastra,Environment=dev,ManagedBy=cli",
            region=args.region)

    aws("lambda", "wait", "function-updated", "--function-name", args.function,
        region=args.region)

    # CORS is configured on the Function URL as well as in the app. The URL layer
    # answers the preflight before the handler is ever invoked, so a mismatch
    # here fails the browser request while every curl against it succeeds.
    cors_config = json.dumps(
        {
            "AllowOrigins": origins,
            "AllowMethods": ["GET", "POST"],
            "AllowHeaders": ["content-type"],
            "MaxAge": 3600,
        }
    )
    try:
        url = json.loads(
            aws("lambda", "create-function-url-config",
                "--function-name", args.function,
                "--auth-type", "NONE",
                "--cors", cors_config,
                region=args.region)
        )
    except RuntimeError:
        url = json.loads(
            aws("lambda", "update-function-url-config",
                "--function-name", args.function,
                "--auth-type", "NONE",
                "--cors", cors_config,
                region=args.region)
        )

    # Without this the Function URL returns 403: the URL's auth type says "no
    # IAM check", but the function's own resource policy still has to allow the
    # public principal to invoke it.
    try:
        aws("lambda", "add-permission",
            "--function-name", args.function,
            "--statement-id", "function-url-public",
            "--action", "lambda:InvokeFunctionUrl",
            "--principal", "*",
            "--function-url-auth-type", "NONE",
            region=args.region)
    except RuntimeError:
        pass  # already granted

    print(url["FunctionUrl"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
