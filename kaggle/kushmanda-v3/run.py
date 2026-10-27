"""Kushmanda v3 on Kaggle's GPU: a bigger model on a bigger permissive corpus.

    kaggle kernels push -p kaggle/kushmanda-v3

Clones this repository at the commit below, then trains with `sati.lm.train
--version v3`. The corpus adds GitHub Security Advisories (CC-BY-4.0) and
ATT&CK Mobile and ICS. The model is about 33M parameters (v2: 16.9M). The
held-out questions are v2's, so the two are compared like for like. Sized to
finish inside one 12-hour Kaggle session: v2 took 4.2 h, and building v3's
corpus takes about 32 minutes.
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
    [sys.executable, "-m", "sati.lm.train", "--version", "v3", "--out", f"{WORK}/out",
     "--root", f"{WORK}/repo", "--cache", f"{WORK}/cache",
     "--width", "512", "--layers", "8", "--heads", "8", "--steps", "4000", "--sft-steps", "2000",
     # Run 1 ran out of memory on Kaggle's 14.6 GiB T4 at batch 32 (the loss over
     # a 16k vocabulary is 1.3 GiB per copy). Same effective batch (64), half the
     # memory; 4,000 steps like v2, so it fits one 12-hour session.
     "--batch", "16", "--accumulate", "4"],
    check=True,
    cwd=f"{WORK}/repo/packages/sati",
)
shutil.rmtree(f"{WORK}/repo", ignore_errors=True)
shutil.rmtree(f"{WORK}/cache", ignore_errors=True)
