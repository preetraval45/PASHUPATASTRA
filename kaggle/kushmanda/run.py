"""Runs on Kaggle's free GPU, sent there by .github/workflows/kaggle-kushmanda.yml.

Clones this repository at the exact commit the workflow names, trains Kushmanda
with `sati.lm.train`, and leaves the results in /kaggle/working/out for the
workflow to download. Nothing here is specific to the machine it runs on.
"""

import shutil
import subprocess
import sys

COMMIT = "__COMMIT__"
REPO = "https://github.com/preetraval45/PASHUPATASTRA.git"
WORK = "/kaggle/working"

subprocess.run(["git", "clone", "--quiet", REPO, f"{WORK}/repo"], check=True)
subprocess.run(["git", "-C", f"{WORK}/repo", "checkout", "--quiet", COMMIT], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "tokenizers", "tiktoken"], check=True)
subprocess.run(
    [sys.executable, "-m", "sati.lm.train", "--out", f"{WORK}/out",
     "--root", f"{WORK}/repo", "--cache", f"{WORK}/cache"],
    check=True,
    cwd=f"{WORK}/repo/packages/sati",
)
shutil.rmtree(f"{WORK}/repo", ignore_errors=True)
shutil.rmtree(f"{WORK}/cache", ignore_errors=True)
