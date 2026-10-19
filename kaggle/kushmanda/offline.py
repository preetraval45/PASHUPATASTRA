"""Kushmanda training on Kaggle with no internet access.

Kaggle notebooks get internet (and GPUs) only on phone-verified accounts, so
this variant needs neither git nor pip. The code, the repository's docs and the
downloaded corpus arrive as the private dataset `sati-kushmanda-data`, built
from this repository by `kaggle/kushmanda/bundle.py`. Whatever the accelerator,
`sati.lm.train` uses it — CUDA if Kaggle granted one, otherwise the CPU.
"""

import os
import shutil
import subprocess
import sys

INPUT = "/kaggle/input"
WORK = "/kaggle/working"


def find(name: str) -> str:
    for base, dirs, _files in os.walk(INPUT):
        if name in dirs:
            return os.path.join(base, name)
    raise FileNotFoundError(f"{name}/ not found under {INPUT}: {os.listdir(INPUT)}")


code, root, cache = find("code"), find("root"), find("cache")
# The cache is read-only where it is mounted; train.py only reads it.
local_cache = f"{WORK}/cache"
shutil.copytree(cache, local_cache, dirs_exist_ok=True)

env = dict(os.environ, PYTHONPATH=code)
args = [sys.executable, "-m", "sati.lm.train", "--out", f"{WORK}/out", "--root", root, "--cache", local_cache]
if os.environ.get("KUSHMANDA_STEPS"):
    args += ["--steps", os.environ["KUSHMANDA_STEPS"]]
subprocess.run(args, check=True, env=env)
shutil.rmtree(local_cache, ignore_errors=True)
