"""Runs on Kaggle (GPU) with the private model `preetraval4518071604/sati-kushmanda` attached.

Clones this repository at the commit it was pushed with and measures
constrained decoding (RP-44) with `sati.lm.constrained_eval`. Writes
/kaggle/working/out/constrained.json. The weights are attached as a private
Kaggle Model input and never leave Kaggle.
"""

import shutil
import subprocess
import sys

COMMIT = "__COMMIT__"
REPO = "https://github.com/preetraval45/PASHUPATASTRA.git"
WORK = "/kaggle/working"

subprocess.run(["git", "clone", "--quiet", REPO, f"{WORK}/repo"], check=True)
subprocess.run(["git", "-C", f"{WORK}/repo", "checkout", "--quiet", COMMIT], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "tokenizers"], check=True)
subprocess.run(
    [sys.executable, "-m", "sati.lm.constrained_eval", "--model", "/kaggle/input",
     "--cache", f"{WORK}/cache", "--out", f"{WORK}/out"],
    check=True,
    cwd=f"{WORK}/repo/packages/sati",
)
shutil.rmtree(f"{WORK}/repo", ignore_errors=True)
shutil.rmtree(f"{WORK}/cache", ignore_errors=True)
