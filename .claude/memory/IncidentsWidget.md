# Android home-screen widget

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

`IncidentsWidget.kt` and `layout/widget_incidents.xml`: a 4x2 widget with open, need-you and critical counts. `IncidentWatch` now always runs and feeds the widget; the More switch only gates notifications (read in `doWork`). `checkNow` runs a one-off check when a widget is placed. Home's own load also refreshes the widget.

## Decisions made

- **Counts are stored in prefs and redrawn from there,** because RemoteViews cannot hold state. Before the first check the widget shows "–", never a guess.
- **The widget is fixed dark,** in the site's dark palette. It does not follow the in-app theme, because RemoteViews colours come from XML and the panel looks right on both light and dark wallpapers.
- **The owner said "keep working" without answering the frontier-model question.** No paid service was enabled; that still waits for an explicit yes.
