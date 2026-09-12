"""AWS Lambda entry point.

Two shapes of event arrive here. An HTTP request from API Gateway, which Mangum
adapts to the ASGI app — the engines, the policy path and the audit trail are
the same objects as under uvicorn, because a deployment target that needed its
own code path would be a second implementation to keep in step.

And a scheduled invocation from EventBridge, which is not a request at all.
Feed polling is deliberately *not* an HTTP route: an endpoint that fetches from
third parties and writes to the store is one anybody on the internet can aim at,
and protecting it would mean inventing a second authentication scheme for the
one caller that is not a person. A scheduler invoking the function directly
needs no secret, because reaching it already requires IAM.
"""

from __future__ import annotations

import logging

from mangum import Mangum

from .main import app

logging.getLogger().setLevel(logging.INFO)

_http = Mangum(app, lifespan="off")

SCHEDULED_TASK = "ingest_feeds"
WARM_TASK = "warm"


def handler(event, context):
    # The tasks live in `app/tasks.py`, which imports nothing Lambda-specific,
    # so they can be tested where `mangum` is not installed.
    from .tasks import ingest, warm

    if isinstance(event, dict) and event.get("task") == SCHEDULED_TASK:
        return ingest()
    if isinstance(event, dict) and event.get("task") == WARM_TASK:
        return warm()
    return _http(event, context)
