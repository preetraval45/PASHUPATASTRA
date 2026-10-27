"""Runs on Kaggle (CPU), with the UNSW-NB15 and CIC-IDS2017 datasets attached.

Clones this repository at the exact commit it was pushed with, trains and
tests Chandraghanta with `sati.netdetect.run`, and leaves `results.json` in
/kaggle/working/out. Kaggle hosts both datasets; their official downloads sit
behind a SharePoint folder and a request form that CI cannot reach.

Attached datasets (kernel-metadata.json): mrwellsdavid/unsw-nb15 and
chethuhn/network-intrusion-dataset. Both are searched for under /kaggle/input
by their distinctive file names, because Kaggle's mount layout has changed
before (the first run looked in /kaggle/input/unsw-nb15 and found nothing).
"""

import shutil
import subprocess
import sys

COMMIT = "__COMMIT__"
REPO = "https://github.com/preetraval45/PASHUPATASTRA.git"
WORK = "/kaggle/working"

print(subprocess.run(["find", "/kaggle/input", "-maxdepth", "4"], capture_output=True, text=True).stdout[:4000])
subprocess.run(["git", "clone", "--quiet", REPO, f"{WORK}/repo"], check=True)
subprocess.run(["git", "-C", f"{WORK}/repo", "checkout", "--quiet", COMMIT], check=True)
# packages/core supplies pashupatastra.trees for the export, with its dependencies (ulid, pydantic).
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-e", f"{WORK}/repo/packages/core"], check=True)
subprocess.run(
    [sys.executable, "-m", "sati.netdetect.run", "--out", f"{WORK}/out",
     "--unsw", "/kaggle/input", "--cic", "/kaggle/input"],
    check=True,
    cwd=f"{WORK}/repo/packages/sati",
)
shutil.rmtree(f"{WORK}/repo", ignore_errors=True)
