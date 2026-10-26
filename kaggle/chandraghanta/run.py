"""Runs on Kaggle (CPU), with the UNSW-NB15 and CIC-IDS2017 datasets attached.

Clones this repository at the exact commit it was pushed with, trains and
tests Chandraghanta with `sati.netdetect.run`, and leaves `results.json` in
/kaggle/working/out. Kaggle hosts both datasets; their official downloads sit
behind a SharePoint folder and a request form that CI cannot reach.

Attached datasets (kernel-metadata.json):
  mrwellsdavid/unsw-nb15                → /kaggle/input/unsw-nb15
  chethuhn/network-intrusion-dataset    → /kaggle/input/network-intrusion-dataset
"""

import shutil
import subprocess
import sys

COMMIT = "__COMMIT__"
REPO = "https://github.com/preetraval45/PASHUPATASTRA.git"
WORK = "/kaggle/working"

subprocess.run(["git", "clone", "--quiet", REPO, f"{WORK}/repo"], check=True)
subprocess.run(["git", "-C", f"{WORK}/repo", "checkout", "--quiet", COMMIT], check=True)
subprocess.run(
    [sys.executable, "-m", "sati.netdetect.run", "--out", f"{WORK}/out",
     "--unsw", "/kaggle/input/unsw-nb15", "--cic", "/kaggle/input/network-intrusion-dataset"],
    check=True,
    cwd=f"{WORK}/repo/packages/sati",
)
shutil.rmtree(f"{WORK}/repo", ignore_errors=True)
