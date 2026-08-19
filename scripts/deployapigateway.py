"""Put an API Gateway HTTP API in front of the Lambda function.

A Lambda Function URL is the cheaper and simpler way to expose the API, and it
is what `deploylambda.py` configures. This exists because some accounts refuse
anonymous invocation of Function URLs: the resource policy is correct, the auth
type is `NONE`, and AWS still answers 403 before the request reaches the
function. An HTTP API is not subject to that, and is the shape the topology in
docs/DEPLOYMENT.md describes anyway.

Cost: 1M requests/month free for the first twelve months, then roughly $1 per
million. At demo traffic the difference from a Function URL is nil.

CORS is set here rather than left to the application. The gateway answers the
preflight itself, so an origin missing from this list fails in a browser while
every `curl` against the same endpoint succeeds — the most confusing way for
this to break.

Usage:  python scripts/deployapigateway.py --cors https://example.com
"""

from __future__ import annotations

import argparse
import json
import subprocess

FUNCTION = "pashupatastra-api"
API_NAME = "pashupatastra-api"
REGION = "us-east-1"

PAYLOAD_VERSION = "2.0"
"""The event shape Mangum expects, and the same one a Function URL sends — so
the handler does not care which of the two is in front of it."""


def aws(*args: str, region: str = REGION) -> dict | list:
    result = subprocess.run(
        ["aws", *args, "--region", region, "--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"aws {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "{}")


def find_api(name: str, region: str) -> dict | None:
    apis = aws("apigatewayv2", "get-apis", region=region)
    return next((a for a in apis.get("Items", []) if a["Name"] == name), None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function", default=FUNCTION)
    parser.add_argument("--name", default=API_NAME)
    parser.add_argument("--region", default=REGION)
    parser.add_argument("--cors", action="append", required=True)
    args = parser.parse_args()

    if "*" in args.cors:
        parser.error("a CORS wildcard is not an acceptable origin; name the dashboard's origin")

    function = aws("lambda", "get-function", "--function-name", args.function,
                   region=args.region)
    function_arn = function["Configuration"]["FunctionArn"]
    account = function_arn.split(":")[4]

    cors = [
        "--cors-configuration",
        f"AllowOrigins={','.join(args.cors)},AllowMethods=GET,POST,OPTIONS,"
        "AllowHeaders=content-type,MaxAge=3600",
    ]

    api = find_api(args.name, args.region)
    if api is None:
        # A quick-create API routes every path to the function with $default,
        # which is what an ASGI app wants: routing belongs to Starlette, and
        # declaring routes here would be a second, drifting copy of them.
        api = aws("apigatewayv2", "create-api",
                  "--name", args.name,
                  "--protocol-type", "HTTP",
                  "--target", function_arn,
                  "--tags", "Project=pashupatastra,Environment=dev,ManagedBy=cli",
                  *cors,
                  region=args.region)
    else:
        aws("apigatewayv2", "update-api", "--api-id", api["ApiId"], *cors,
            region=args.region)

    api_id = api["ApiId"]

    # Quick-create adds the invoke permission itself, but only on creation. An
    # existing API that lost the statement would fail with 500 and nothing in
    # the gateway logs to say why.
    try:
        aws("lambda", "add-permission",
            "--function-name", args.function,
            "--statement-id", f"apigateway-{api_id}",
            "--action", "lambda:InvokeFunction",
            "--principal", "apigateway.amazonaws.com",
            "--source-arn", f"arn:aws:execute-api:{args.region}:{account}:{api_id}/*/*",
            region=args.region)
    except RuntimeError:
        pass  # already granted

    print(f"https://{api_id}.execute-api.{args.region}.amazonaws.com")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
