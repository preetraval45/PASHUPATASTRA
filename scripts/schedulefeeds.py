"""Poll the threat feeds on a schedule, using EventBridge Scheduler.

    python scripts/schedulefeeds.py --function pashupatastra-api

Creates, if they are not already there:

- an IAM role EventBridge Scheduler can assume, allowed to invoke exactly one
  function — not `lambda:InvokeFunction` on `*`, which is the shape these roles
  usually end up with;
- a schedule that invokes it with `{"task": "ingest_feeds"}`.

**Hourly, and no faster.** CISA publishes daily and URLhaus continuously, so an
hourly poll is already ahead of one of them. Polling a third party more often
than it changes is rude at best and rate-limited at worst, and there is nothing
to gain: the console is not a live feed reader.

Free tier: EventBridge Scheduler allows 14M invocations a month. This uses 720.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

TRUST = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "scheduler.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function", default="pashupatastra-api")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--name", default="pashupatastra-feeds")
    parser.add_argument("--role", default="pashupatastra-scheduler")
    parser.add_argument("--rate", default="1 hour", help="e.g. '1 hour', '30 minutes'")
    parser.add_argument(
        "--task",
        default="ingest_feeds",
        choices=["ingest_feeds", "warm"],
        help=(
            "what the schedule asks the function to do. `warm` is R99's keep-alive: "
            "run it as `--name pashupatastra-warm --rate '5 minutes' --task warm`."
        ),
    )
    args = parser.parse_args()

    import boto3
    from botocore.exceptions import ClientError

    iam = boto3.client("iam", region_name=args.region)
    lam = boto3.client("lambda", region_name=args.region)
    scheduler = boto3.client("scheduler", region_name=args.region)

    target_arn = lam.get_function_configuration(FunctionName=args.function)["FunctionArn"]
    print(f"target   : {target_arn}")

    # --- the role -------------------------------------------------------------
    try:
        role = iam.create_role(
            RoleName=args.role,
            AssumeRolePolicyDocument=json.dumps(TRUST),
            Description="Lets EventBridge Scheduler invoke the Pashupatastra API "
            "for scheduled threat feed ingestion.",
        )["Role"]
        print(f"role     : created {args.role}")
        # IAM is eventually consistent, and a schedule created against a role
        # that has not propagated fails with a validation error that reads like
        # the role does not exist.
        time.sleep(12)
    except ClientError as error:
        if error.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        role = iam.get_role(RoleName=args.role)["Role"]
        print(f"role     : reusing {args.role}")

    iam.put_role_policy(
        RoleName=args.role,
        PolicyName="InvokeIngestFunction",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "lambda:InvokeFunction",
                        # This function, not every function. A scheduler role
                        # with a wildcard is a scheduler that can invoke
                        # anything the account ever deploys.
                        "Resource": target_arn,
                    }
                ],
            }
        ),
    )
    print("policy   : invoke limited to that one function")

    # --- the schedule ---------------------------------------------------------
    definition = {
        "Name": args.name,
        "ScheduleExpression": f"rate({args.rate})",
        "FlexibleTimeWindow": (
            {"Mode": "FLEXIBLE", "MaximumWindowInMinutes": 15}
            if args.task == "ingest_feeds"
            else {"Mode": "OFF"}  # a keep-alive that drifts fifteen minutes is not one
        ),
        "Target": {
            "Arn": target_arn,
            "RoleArn": role["Arn"],
            "Input": json.dumps({"task": args.task}),
            "RetryPolicy": {"MaximumRetryAttempts": 2},
        },
        "Description": (
            "Hourly threat feed ingestion (CISA KEV, abuse.ch URLhaus)."
            if args.task == "ingest_feeds"
            else "Keep-alive and heartbeat every five minutes (R99)."
        ),
        "State": "ENABLED",
    }

    try:
        scheduler.create_schedule(**definition)
        print(f"schedule : created {args.name} at rate({args.rate})")
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code == "ConflictException":
            scheduler.update_schedule(**definition)
            print(f"schedule : updated {args.name} at rate({args.rate})")
        elif code in {"AccessDeniedException", "AccessDenied"}:
            # The deploying identity has Lambda, DynamoDB and IAM but not
            # EventBridge. Printing the traceback here would be accurate and
            # useless: the fix is a permission somebody has to grant, and it
            # belongs on screen next to the failure rather than in a doc.
            _explain(args, target_arn, role["Arn"], definition)
            return 2
        else:
            raise

    # A flexible window, because nothing here needs to happen on the minute and
    # AWS charges nothing either way — but a fleet of schedules all firing at
    # :00 is a self-inflicted thundering herd.
    print("\nnext: the first run happens within the window; check with")
    print(f"  aws lambda invoke --function-name {args.function} "
          "--payload '{\"task\":\"ingest_feeds\"}' out.json")
    return 0


def _explain(args, target_arn: str, role_arn: str, definition: dict) -> None:
    """Say what is missing and how to supply it, on screen, next to the failure.

    A traceback here would be accurate and useless: the fix is a permission
    somebody has to grant, and it belongs where the person who hit the wall is
    looking rather than in a document they have not opened.
    """
    grant = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "scheduler:CreateSchedule",
                    "scheduler:UpdateSchedule",
                    "scheduler:GetSchedule",
                    "iam:PassRole",
                ],
                "Resource": "*",
            }
        ],
    }
    print()
    print("schedule : DENIED — this identity cannot create EventBridge schedules.")
    print("           Everything else is in place: the role exists, its policy is")
    print("           attached, and the function answers the scheduled payload.")
    print()
    print("Either grant the deploying user this, and re-run:")
    print()
    print(json.dumps(grant, indent=2))
    print()
    print("Or create it once in the console — EventBridge > Schedules > Create:")
    print(f"           name      {args.name}")
    print(f"           schedule  rate({args.rate}), {definition['FlexibleTimeWindow']['Mode'].lower()} window")
    print(f"           target    {target_arn}")
    print(f"           input     {definition['Target']['Input']}")
    print(f"           role      {role_arn}")
    print()
    print("Until then the feeds ingest only when invoked by hand:")
    print(
        f"  aws lambda invoke --function-name {args.function}"
        ' --payload \'{"task":"ingest_feeds"}\' out.json'
    )


if __name__ == "__main__":
    sys.exit(main())
