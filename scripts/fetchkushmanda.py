"""Fetch Kushmanda's weights from Kaggle and export them for the API's numpy engine (CI deploy step).

Into a git-ignored folder, services/api/app/sati_models/kushmanda: they reach the Lambda archive and
nothing else. Run by .github/workflows/ci.yml with KAGGLE_USERNAME and KAGGLE_API_TOKEN set; a failure
here is reported and the API deploys without Kushmanda rather than not at all.

Usage:  PYTHONPATH=packages/sati python scripts/fetchkushmanda.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

MODEL = "preetraval4518071604/sati-kushmanda/pyTorch/v2/1"
OUT = Path("services/api/app/sati_models/kushmanda")


def main() -> int:
    # kagglehub, not the kaggle CLI: the CLI's bulk download endpoint answers 404 for this model version
    # (2 Nov 2026) while listing its files works; kagglehub fetches the files one by one.
    import kagglehub

    WORK = Path(kagglehub.model_download(MODEL))
    files = sorted(p.relative_to(WORK).as_posix() for p in WORK.rglob("*") if p.is_file())
    print("downloaded:", files)
    checkpoint = next(WORK.rglob("*.pt"), None)
    tokenizer = next(WORK.rglob("tokenizer.json"), None)
    if checkpoint is None or tokenizer is None:
        print(f"expected a .pt checkpoint and tokenizer.json, found {files}", file=sys.stderr)
        return 1

    import torch

    from sati.lm.infer import export

    ckpt = torch.load(checkpoint, map_location="cpu")
    export(ckpt["state"], ckpt["config"], OUT)
    shutil.copy(tokenizer, OUT / "tokenizer.json")
    print("Kushmanda exported:", sorted(p.name for p in OUT.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
