"""AWS operations run from CI with the repository's AWS secrets (.github/workflows/aws-ops.yml).

The keys exist only as GitHub secrets, so work on the AWS account happens here, in a workflow, and is
asked for by committing `.github/aws-ops.json`:

    {"ops": ["status", "ses-status"], "email": "sender@example.com"}

Each operation prints its findings as GitHub annotations (`::notice::`), which the Checks API shows for a
public repository without signing in. Read-only operations: `status`, `ses-status`. Operations that change
the account say so in their name: `ses-verify` (asks SES to send `email` a confirmation link) and
`ses-permission` (lets the API's Lambda role send email through SES).

Never prints a key, a secret or an environment variable's value: only names, counts and states.

Usage:  python scripts/awsops.py .github/aws-ops.json
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

import boto3

REGION = "us-east-1"
FUNCTION = "pashupatastra-api"
TABLE = "pashupatastra"


def note(title: str, message: str, level: str = "notice") -> None:
    print(f"::{level} title={title}::{message}".replace("\n", " "))


def status(hours: float = 24) -> None:
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_configuration(FunctionName=FUNCTION)
    names = sorted(config.get("Environment", {}).get("Variables", {}))
    note("Lambda", f"{config['Runtime']}, {config['MemorySize']} MB, timeout {config['Timeout']}s, "
         f"code {config['CodeSize'] // 1024} KB, last modified {config['LastModified']}; env names: {', '.join(names)}")

    logs = boto3.client("logs", region_name=REGION)
    since = int((datetime.now(UTC) - timedelta(hours=hours)).timestamp() * 1000)
    errors = 0
    try:
        pages = logs.get_paginator("filter_log_events").paginate(
            logGroupName=f"/aws/lambda/{FUNCTION}", startTime=since, filterPattern='?ERROR ?Traceback ?"Task timed out"')
        kinds: dict[str, int] = {}
        where: dict[str, str] = {}
        for page in pages:
            for event in page.get("events", []):
                errors += 1
                text = event["message"].replace("\r", "")
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                # The exception is the traceback's last line; the frame above it says where.
                last = next((line for line in reversed(lines) if ("Error" in line or "Exception" in line)
                             and not line.startswith("File ")), lines[-1] if lines else "?")
                frames = [line for line in lines if line.startswith("File ")]
                key = last[:600]
                kinds[key] = kinds.get(key, 0) + 1
                where.setdefault(key, frames[-1][:200] if frames else "")
        note(f"Lambda errors ({hours:g}h)", f"{errors} error lines", "warning" if errors else "notice")
        for key, count in sorted(kinds.items(), key=lambda kv: -kv[1])[:6]:
            note("Lambda error", f"{count}x {key} at {where[key]}", "warning")
    except logs.exceptions.ResourceNotFoundException:
        note("Lambda errors (24h)", "no log group yet")

    table = boto3.client("dynamodb", region_name=REGION).describe_table(TableName=TABLE)["Table"]
    note("DynamoDB", f"{table['ItemCount']} items, {table['TableSizeBytes'] // 1024} KB, "
         f"billing {table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')} (counts refresh about every 6h)")

    gw = boto3.client("apigatewayv2", region_name=REGION)
    for api in gw.get_apis()["Items"]:
        cors = api.get("CorsConfiguration", {})
        note("API Gateway", f"{api['Name']}: origins {cors.get('AllowOrigins')}, methods {cors.get('AllowMethods')}, "
             f"headers {cors.get('AllowHeaders')}")


def ses_status() -> None:
    ses = boto3.client("sesv2", region_name=REGION)
    account = ses.get_account()
    note("SES account", f"production access {account.get('ProductionAccessEnabled')}, sending enabled "
         f"{account.get('SendingEnabled')}, quota {account.get('SendQuota', {}).get('Max24HourSend')} per day")
    identities = ses.list_email_identities().get("EmailIdentities", [])
    if not identities:
        note("SES identities", "none: no sender is verified yet")
    for identity in identities:
        note("SES identity", f"{identity['IdentityName']} ({identity['IdentityType']}): "
             f"verified {identity.get('VerificationStatus')}, sending {identity.get('SendingEnabled')}")


def ses_verify(email: str) -> None:
    """Asks SES to email `email` a confirmation link. Changes the account: adds an identity."""
    if not email or "@" not in email:
        note("SES verify", "no sender email given in aws-ops.json", "error")
        return
    boto3.client("sesv2", region_name=REGION).create_email_identity(EmailIdentity=email)
    note("SES verify", f"confirmation link sent to {email}; it must be clicked before SES will send from it")


def ses_permission() -> None:
    """Lets the API's Lambda role send email through SES. Changes the account: an inline role policy."""
    role = boto3.client("lambda", region_name=REGION).get_function_configuration(FunctionName=FUNCTION)["Role"]
    name = role.rsplit("/", 1)[-1]
    boto3.client("iam").put_role_policy(
        RoleName=name,
        PolicyName="pashupatastra-ses-send",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": ["ses:SendEmail"], "Resource": "*"}],
        }),
    )
    note("SES permission", f"role {name} may now call ses:SendEmail")


def role_policies() -> None:
    """Read-only: the API's Lambda role, and the actions its policies allow."""
    iam = boto3.client("iam")
    arn = boto3.client("lambda", region_name=REGION).get_function_configuration(FunctionName=FUNCTION)["Role"]
    name = arn.rsplit("/", 1)[-1]
    attached = [p["PolicyName"] for p in iam.list_attached_role_policies(RoleName=name)["AttachedPolicies"]]
    note("Lambda role", f"{name}: attached {attached}")
    for policy in iam.list_role_policies(RoleName=name)["PolicyNames"]:
        doc = iam.get_role_policy(RoleName=name, PolicyName=policy)["PolicyDocument"]
        statements = doc.get("Statement", [])
        statements = statements if isinstance(statements, list) else [statements]
        for st in statements:
            actions = st.get("Action", [])
            actions = actions if isinstance(actions, list) else [actions]
            note("Lambda role inline", f"{policy}: {st.get('Effect')} {sorted(actions)} on {st.get('Resource')}")


def main() -> int:
    request = json.loads(open(sys.argv[1], encoding="utf-8").read())
    ops = {"status": lambda: status(float(request.get("hours", 24))), "role-policies": role_policies, "ses-status": ses_status, "ses-permission": ses_permission,
           "ses-verify": lambda: ses_verify(request.get("email", ""))}
    failed = False
    for name in request.get("ops", []):
        try:
            ops[name]()
        except KeyError:
            note(name, "unknown operation", "error")
            failed = True
        except Exception as exc:  # noqa: BLE001 - report every operation, then fail the run
            note(name, f"{type(exc).__name__}: {str(exc)[:300]}", "error")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
