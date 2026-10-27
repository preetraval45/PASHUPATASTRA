"""Brahmacharini v1 on Kaggle's GPU: a transformer encoder beside v0, same split.

    kaggle kernels push -p kaggle/brahmacharini-v1

Clones this repository at the commit below and runs `sati.embed.run --arch
transformer`, which trains v0 (the bag of words) and v1 (about 20M parameters)
on the same split, then scores both on the same held-out procedures.
"""

import subprocess
import sys

COMMIT = "__COMMIT__"
REPO = "https://github.com/preetraval45/PASHUPATASTRA.git"
WORK = "/kaggle/working"

subprocess.run(["git", "clone", "--quiet", REPO, f"{WORK}/repo"], check=True)
subprocess.run(["git", "-C", f"{WORK}/repo", "checkout", "--quiet", COMMIT], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-e", f"{WORK}/repo/packages/core"], check=True)
subprocess.run(
    [sys.executable, "-m", "sati.embed.run", "--arch", "transformer", "--epochs", "30",
     "--cache", f"{WORK}/cache", "--out", f"{WORK}/out"],
    check=True,
    cwd=f"{WORK}/repo/packages/sati",
)
