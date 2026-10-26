#!/usr/bin/env bash
# Commit generated results to main from a workflow, safely against parallel jobs.
#
#     bash scripts/pushresults.sh "<commit message>" <file or folder>...
#
# Every training and data workflow ends by committing what it generated. Jobs
# run in parallel and runs overlap, so `git pull --rebase` used to meet a
# conflict on a results file another job had just written, then fail six
# times (26 Oct). Before that, a loop ending in `sleep` exited 0 and hid a lost
# push (19 Oct).
#
# The approach: generated files are never merged. They are saved, the checkout
# is reset to the newest main, the saved files are laid over it, and the commit
# is pushed. Pass exact files, or folders this job alone owns: a whole shared
# folder would write this job's stale copies of other jobs' files over newer
# ones.
set -u

message=$1
shift
stash=$(mktemp -d)
tar -cf "$stash/results.tar" -- "$@"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3 4 5 6; do
  git fetch -q origin main && git reset -q --hard origin/main && tar -xf "$stash/results.tar"
  # -f: benchmark/results is gitignored on purpose and committed on purpose.
  git add -f -- "$@"
  if git diff --cached --quiet; then
    echo "results unchanged"
    exit 0
  fi
  git commit -q -m "$message" && git push -q origin HEAD:main && echo "pushed: $message" && exit 0
  sleep $((attempt * 15))
done
echo "::error::could not push the results after 6 attempts"
exit 1
