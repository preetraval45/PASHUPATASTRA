"""Katyayani on Kaal (RP-24): the graph features and their provenance."""

from __future__ import annotations

from pashupatastra.kaal.generator import incident

from sati.rca.kaal import FEATURES, featurise, wilson


def _with_root(start: int = 0):
    i = start
    while True:
        inc = incident(5, i)
        if inc.label["root_service"] is not None:
            return inc
        i += 1


def test_one_row_per_service_with_exactly_one_root():
    inc = _with_root()
    table, _ = featurise(inc)
    assert len(table) == len(inc.services)
    assert table["label"].sum() == 1
    assert set(FEATURES) <= set(table.columns)


def test_every_feature_traces_to_real_event_ids():
    inc = _with_root(10)
    _, provenance = featurise(inc)
    ids = {e.id for e in inc.events}
    assert all(set(v) <= ids for v in provenance.values())
    root = inc.label["root_service"]
    assert provenance[root], "the root's features must cite the events behind them"


def test_the_root_usually_has_anomalous_callers_rather_than_callees():
    callers = callees = 0
    for i in range(200):
        inc = incident(5, i)
        if inc.label["root_service"] is None:
            continue
        table, _ = featurise(inc)
        row = table[table["label"] == 1].iloc[0]
        callers += row["anomalous_callers"] > 0
        callees += row["anomalous_callees"] > 0
    assert callers > callees


def test_wilson_interval_brackets_the_rate():
    lo, hi = wilson(90, 100)
    assert lo < 0.9 < hi and 0 <= lo and hi <= 1
