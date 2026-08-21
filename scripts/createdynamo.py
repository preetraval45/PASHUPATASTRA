"""Create the DynamoDB table the API persists to.

**Provisioned, not on-demand, and that is the whole reason this is DynamoDB.**
The always-free allowance is 25 read and 25 write capacity units on provisioned
tables; on-demand has no perpetual free tier. RDS would have been the obvious
choice and its free tier expires after twelve months — see docs/REBUILD.md.

One table, because every access pattern here is a lookup by id or a listing of
one type in time order, and a second table would buy nothing but a second thing
to keep in step.

    PK        SK                          what
    INCIDENT  <incident id>               one incident
    AUDIT     <iso timestamp>#<seq>       one audit record, ordered by time
    EVENT     <event id>                  one observation
    NODE      <entity key>                one topology node
    EDGE      <source>|<target>|<kind>    one topology edge
    META      SEED#<version>              the marker that says seeding ran

`seq` is in the audit sort key because two records written in the same
millisecond would otherwise overwrite each other, and an audit trail that drops
a record under load is not an audit trail.

One index, `ByEntity`, for "what has this entity been saying" — the only query
that is not answerable from the table's own keys.

Usage:  python scripts/createdynamo.py [--table pashupatastra] [--region us-east-1]
"""

from __future__ import annotations

import argparse
import time

TABLE = "pashupatastra"
REGION = "us-east-1"

READ_CAPACITY = 25
WRITE_CAPACITY = 25
"""The exact always-free allowance. Raising either starts a bill; the demo's
whole traffic is a handful of reads per page view."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default=TABLE)
    parser.add_argument("--region", default=REGION)
    args = parser.parse_args()

    import boto3
    from botocore.exceptions import ClientError

    dynamodb = boto3.client("dynamodb", region_name=args.region)

    try:
        existing = dynamodb.describe_table(TableName=args.table)["Table"]
        print(f"{args.table} already exists — {existing['TableStatus']}, "
              f"{existing['ItemCount']} items")
        return 0
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    dynamodb.create_table(
        TableName=args.table,
        BillingMode="PROVISIONED",
        ProvisionedThroughput={
            "ReadCapacityUnits": READ_CAPACITY,
            "WriteCapacityUnits": WRITE_CAPACITY,
        },
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "ByEntity",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                # An index has its own capacity, and it also counts against the
                # free allowance. Split rather than doubled.
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        Tags=[
            {"Key": "Project", "Value": "pashupatastra"},
            {"Key": "ManagedBy", "Value": "cli"},
        ],
    )
    print(f"creating {args.table}…")

    while True:
        table = dynamodb.describe_table(TableName=args.table)["Table"]
        if table["TableStatus"] == "ACTIVE":
            break
        time.sleep(3)

    print(f"{args.table} active in {args.region}")
    print(f"  capacity  {READ_CAPACITY} read / {WRITE_CAPACITY} write (provisioned, free tier)")
    print("  index     ByEntity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
