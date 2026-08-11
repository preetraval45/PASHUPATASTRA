"""Export the OpenAPI document to `openapi.json`.

The exported file is committed and checked in CI. FastAPI generates the spec
from the code, so the file cannot drift from the implementation — but it can
drift from what consumers were promised, and that is what the CI check catches:
any change to the public surface shows up as a diff in review rather than
breaking a client silently.

Usage:  python -m app.exportopenapi [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .main import app

SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export or verify the OpenAPI document")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed spec differs from the current code",
    )
    args = parser.parse_args()
    current = render()

    if args.check:
        if not SPEC_PATH.exists():
            print("openapi.json is missing — run: python -m app.exportopenapi")
            return 1
        if SPEC_PATH.read_text(encoding="utf-8") != current:
            print(
                "openapi.json is out of date. The API surface changed.\n"
                "Regenerate with: python -m app.exportopenapi"
            )
            return 1
        print("openapi.json is current")
        return 0

    SPEC_PATH.write_text(current, encoding="utf-8")
    print(f"wrote {SPEC_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
