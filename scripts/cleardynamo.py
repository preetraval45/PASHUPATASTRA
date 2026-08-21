"""Empty a namespace in the DynamoDB table.

For re-seeding after the scenarios change shape, and for removing data written
before `dynamo_namespace` existed — that data sits under bare partition keys
(`NODE`, `AUDIT`) rather than namespaced ones (`prod#NODE`), which is what
`--legacy` targets.

Deletes nothing without `--yes`.

    python scripts/cleardynamo.py --namespace test
    python scripts/cleardynamo.py --legacy --yes
"""

from __future__ import annotations

import argparse
import sys

PARTITIONS = ("INCIDENT", "AUDIT", "EVENT", "NODE", "EDGE", "META")


def rows(table, pk: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key

    found: list[dict] = []
    kwargs = {"KeyConditionExpression": Key("PK").eq(pk)}
    while True:
        page = table.query(**kwargs)
        found += page["Items"]
        if "LastEvaluatedKey" not in page:
            return found
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default="pashupatastra")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--namespace", default="test")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="target bare partition keys, written before namespacing existed",
    )
    parser.add_argument("--yes", action="store_true", help="actually delete")
    args = parser.parse_args()

    import boto3

    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    label = "legacy (un-namespaced)" if args.legacy else args.namespace

    targets = {p: rows(table, p if args.legacy else f"{args.namespace}#{p}") for p in PARTITIONS}
    total = sum(len(v) for v in targets.values())

    print(f"{args.table} / {label}")
    for partition, found in targets.items():
        if found:
            print(f"  {partition:9} {len(found)}")
    if not total:
        print("  nothing to remove")
        return 0

    if not args.yes:
        print(f"\n{total} rows would be deleted. Re-run with --yes.")
        return 0

    with table.batch_writer() as batch:
        for found in targets.values():
            for row in found:
                batch.delete_item(Key={"PK": row["PK"], "SK": row["SK"]})
    print(f"\ndeleted {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
