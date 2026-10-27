"""RP-19's live stack: the plan is locked, the manifest is valid, and the shape is new."""

from __future__ import annotations

import json
import sys
from collections import Counter

import yaml
from pashupatastra.kaal.dataset import REFERENCE_SHAPES, shape, shape_of
from pashupatastra.kaal.generator import incident

from benchmark.live import app, plan, topology


def _live_shape() -> str:
    nodes = [(s, topology.LAYER.get(s, "backend"), topology.KIND.get(s, "service")) for s in topology.SERVICES]
    return shape_of(nodes, topology.CALLS)


def test_the_committed_plan_matches_its_hash_and_is_balanced():
    p = plan.load()
    assert p["incidents"] == plan.make()
    assert Counter(i["fault"] for i in p["incidents"]) == {f: plan.N // len(plan.FAULTS) for f in plan.FAULTS}
    assert {i["root"] for i in p["incidents"]} <= set(topology.SERVICES)


def test_an_edited_plan_is_refused(tmp_path):
    p = json.loads(plan.PLAN.read_text(encoding="utf-8"))
    p["incidents"][0]["root"] = "web" if p["incidents"][0]["root"] != "web" else "db"
    edited = tmp_path / "plan.json"
    edited.write_text(json.dumps(p), encoding="utf-8")
    try:
        plan.load(edited)
    except ValueError:
        return
    raise AssertionError("an edited plan loaded")


def test_the_manifest_parses_and_wires_each_service_to_its_callees():
    docs = [d for d in yaml.safe_load_all(topology.manifest("live-x")) if d]
    deployments = {d["metadata"]["name"]: d for d in docs if d["kind"] == "Deployment"}
    assert set(deployments) == {*topology.SERVICES, "loadgen", "collector"}
    assert all(d["metadata"].get("namespace") == "live-x" for d in docs if d["kind"] != "Namespace")
    env = {e["name"]: e["value"] for e in deployments["orders"]["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["DOWNSTREAM"].split(",") == ["stock", "billing", "account"]
    config = next(d for d in docs if d["kind"] == "ConfigMap")
    assert config["data"]["app.py"].strip() == topology.APP.read_text(encoding="utf-8").strip()


def test_the_live_shape_matches_no_reference_and_no_kaal_topology():
    live = _live_shape()
    assert live not in REFERENCE_SHAPES.values()
    assert all(shape(incident(1, i)) != live for i in range(2000))


def test_cgroup_usage_is_read_from_the_container(tmp_path):
    (tmp_path / "cpu.stat").write_text("usage_usec 2500000\nuser_usec 2000000\n")
    (tmp_path / "memory.current").write_text("1048576\n")
    assert app.usage(str(tmp_path)) == (2.5, 1048576.0, "cgroup")
    if sys.platform != "win32":  # the fallback reads POSIX `resource`; the service runs on Linux
        assert app.usage(str(tmp_path / "absent"))[2] == "process"


def test_p90():
    assert app.p90([]) == 0.0
    assert app.p90([float(i) for i in range(1, 11)]) == 10.0
