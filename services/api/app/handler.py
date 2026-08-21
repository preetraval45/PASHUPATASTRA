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


def handler(event, context):
    if isinstance(event, dict) and event.get("task") == SCHEDULED_TASK:
        return _ingest()
    return _http(event, context)


def _ingest() -> dict[str, object]:
    """Poll the threat feeds. Imported inside the branch so an HTTP request
    never pays for modules it will not use."""
    from .backend import durable
    from .feeds.ingest import cursors_for, run
    from .graph import entitystore

    backend = durable()
    summary = run(store=entitystore(), cursors=cursors_for(backend), limit=25)
    logging.getLogger(__name__).info("feed ingest: %s", summary)
    return {"task": SCHEDULED_TASK, "feeds": summary, "durable": backend is not None}
