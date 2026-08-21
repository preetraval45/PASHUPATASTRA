"""Test-wide guards.

Set before any test module imports `app`, because importing `app.main` runs the
demo seed as a side effect of import — under a configured table that seed writes
to whatever namespace the settings name, and the default names the deployed one.
That is not hypothetical: it put an incident into `prod` on the run that added
these tests.
"""

from __future__ import annotations

import os

os.environ.setdefault("PASHU_DYNAMO_NAMESPACE", "test")
