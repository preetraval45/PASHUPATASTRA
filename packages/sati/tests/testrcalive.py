"""RP-19: live-stack records become features with no answer in them, and the right service stands out."""

from __future__ import annotations

from sati.rca.live import features, frame_of

GRAPH = {"calls": [("web", "orders"), ("orders", "db")], "layer": {"web": "edge", "db": "store"}, "kind": {}}
INJECT = 1_000_000


def record(fault_on: str = "orders", deployed: bool = False) -> dict:
    samples = []
    for t in range(INJECT - 120, INJECT + 150, 5):
        for svc in ("web", "orders", "db"):
            hot = svc == fault_on and t >= INJECT
            samples.append({"t": t, "service": svc, "up": 1, "cpu": 0.9 if hot else 0.05 + (t % 7) / 1000,
                            "mem": 3e7, "latency-90": 400.0 if hot else 10 + (t % 3), "request": 15.0,
                            "error": 0.0, "source": "cgroup"})
    deploys = {"orders": [INJECT - 400] + ([INJECT + 2] if deployed else [])}
    return {"id": "live-test", "root": fault_on, "fault": "cpu", "inject_time": INJECT,
            "window": {"before": 120, "after": 150}, "deploys": deploys, "samples": samples}


def test_frame_is_in_rcaeval_layout():
    frame = frame_of(record())
    assert "time" in frame and "orders_cpu" in frame and "db_latency-90" in frame


def test_features_carry_no_answer_and_the_root_is_loudest():
    table, k = features(record(), GRAPH)
    assert "label" not in k and "root" not in k and "fault" not in k
    assert k.set_index("service")["peak"].idxmax() == "orders"


def test_deploy_before_counts_only_deploys_inside_the_window():
    _, quiet = features(record(), GRAPH)
    _, released = features(record(deployed=True), GRAPH)
    assert quiet.set_index("service")["deploy_before"].sum() == 0  # the stack's own creation is outside it
    assert released.set_index("service").loc["orders", "deploy_before"] == 1


def test_pooled_live_table_labels_exactly_one_root_per_incident(tmp_path):
    import gzip
    import json

    from sati.rca.pooled import live_table

    (tmp_path / "meta.json").write_text(json.dumps({"graph": GRAPH}), encoding="utf-8")
    with gzip.open(tmp_path / "incidents.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps(record()) + "\n")
        f.write(json.dumps({"id": "live-bad", "error": "shard failed"}) + "\n")
    table = live_table(tmp_path)
    assert set(table["system"]) == {"live"} and table.groupby("case")["label"].sum().tolist() == [1]
    assert "deploy_before" not in table  # no feature the RCAEval systems lack
