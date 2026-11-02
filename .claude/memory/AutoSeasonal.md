# Automatic period detection (AutoSeasonal)

- **Date:** 2026-11-02
- **Phase:** Phase 2.1 backlog — detection (adr/Seasonality "Owed")
- **Commit(s):** pending

## What changed

`pashupatastra/period.py` (autocorrelation, built to abstain) and `strategies.AutoSeasonal` (robust-z until two agreeing checks, then SeasonalRobustZ primed with history). `sati.seasonal.run`/`report` score robust-z, auto-seasonal and seasonal-robust-z@288 on every real NAB series; `auto-seasonal` job in train-sati.yml commits docs/research/models/auto-seasonal.{md,results.json}.

## Why

The ADR kept seasonal detection opt-in because a wrong period = silent blindness, and owed automatic detection once validated on labelled data.

## Decisions made

- Hills, not local maxima, and the top located on a smoothed ACF: noise bumps on a rising edge gave 58 for 60 before.
- Twice-the-lag recurrence + prominence rejects trends, walks and irregular level shifts; a perfectly regular staircase is detected (genuinely periodic after detrending) and harmless.
- Checks at geometric history lengths (×1.25), capped history 3 weeks of 5-min samples — keeps it cheap online.
- Default stays robust-z until NAB says auto never misses what robust-z caught.

## Open questions

- If NAB shows a blinded series, is it a wrong period or warm-up? The report lists the series.

## Next session should

- Read docs/research/models/auto-seasonal.md after the train-sati run; decide the default with the owner's ADR in mind; tick the backlog item.
