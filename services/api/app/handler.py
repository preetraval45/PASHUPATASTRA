"""AWS Lambda entry point.

Mangum adapts the ASGI app to the Lambda event shape. Nothing else differs from
running under uvicorn — the engines, the policy path, and the audit trail are
the same objects, because a deployment target that needed its own code path
would be a second implementation to keep in step.

`lifespan="off"`: the app declares no startup or shutdown hooks, and Mangum's
lifespan handling would otherwise run on every cold start for nothing.
"""

from __future__ import annotations

from mangum import Mangum

from .main import app

handler = Mangum(app, lifespan="off")
