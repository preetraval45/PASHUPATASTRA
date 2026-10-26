# Kalaratri BGL results; RP-62 done

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models
- **Commit(s):** pending

## What changed

BGL's first run is in (run 40347301393), RP-62 is ticked, and the Kalaratri card
has a BGL section. The Models page shows HDFS and BGL as separate tables. The
BGL report shows each top template's text, starting from the next run, and its
reading note is about BGL instead of HDFS.

## Why

On BGL under a time split, F1 is 0.355, with recall of only 0.27. The baselines
reach high recall only by flagging 77–87% of normal windows. The card says
plainly that Kalaratri misses most failures. Results that look better than
they are would fail the O-1 evidence review.

## Next session should

- Try a Drain-style template parser and measure it before claiming it helps.
- Consider sliding windows, or session windows by node, for BGL.
