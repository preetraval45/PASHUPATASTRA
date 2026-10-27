"""Builds the public Kaggle datasets that need downloads or compute (CPU, internet).

    kaggle kernels push -p kaggle/datasets-builder

Clones this repository at the commit below and runs `scripts/kaggledatasets.py`
for the ATT&CK, grounded-QA and SMD datasets. The output folders, each with its
`dataset-metadata.json`, are published from /kaggle/working/datasets.
"""

import shutil
import subprocess
import sys

COMMIT = "__COMMIT__"
REPO = "https://github.com/preetraval45/PASHUPATASTRA.git"
WORK = "/kaggle/working"

subprocess.run(["git", "clone", "--quiet", REPO, f"{WORK}/repo"], check=True)
subprocess.run(["git", "-C", f"{WORK}/repo", "checkout", "--quiet", COMMIT], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-e", f"{WORK}/repo/packages/core",
                "lightgbm", "pyarrow"], check=True)
subprocess.run([sys.executable, "scripts/kaggledatasets.py", "--out", f"{WORK}/datasets", "--cache", f"{WORK}/cache",
                "--only", "brahmacharini", "skandamata", "kushmanda", "smd"], check=True, cwd=f"{WORK}/repo")
shutil.rmtree(f"{WORK}/repo", ignore_errors=True)
shutil.rmtree(f"{WORK}/cache", ignore_errors=True)
