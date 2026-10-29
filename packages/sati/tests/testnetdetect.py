"""Chandraghanta v0 — the flow loaders, the splits and the per-family scoring, on synthetic files."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sati.netdetect.run import per_family, threshold, validation_mask
from sati.sources import netflow


def _unsw_frame(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    attack = rng.random(n) < 0.4
    return pd.DataFrame({
        "id": range(n), "dur": rng.random(n), "proto": rng.choice(["tcp", "udp"], n),
        "service": rng.choice(["-", "http"], n), "state": rng.choice(["FIN", "INT"], n),
        "sbytes": rng.integers(0, 9000, n), "sttl": np.where(attack, 254, 31), "dttl": 29, "ct_state_ttl": 1,
        "attack_cat": np.where(attack, "Exploits", "Normal"), "label": attack.astype(int),
    })


def test_unsw_takes_the_larger_official_file_as_training(tmp_path):
    _unsw_frame(300, 0).to_csv(tmp_path / "UNSW_NB15_testing-set.csv", index=False)  # swapped names, as released
    _unsw_frame(120, 1).to_csv(tmp_path / "UNSW_NB15_training-set.csv", index=False)
    data = netflow.unsw(tmp_path)
    assert len(data["train"]) == 300 and data["files"]["train"] == "UNSW_NB15_testing-set.csv"
    assert set(data["train"]["family"]) == {"Exploits", "Normal"}


def test_unsw_features_code_categories_from_training_and_can_drop_ttl():
    train, test = _unsw_frame(50, 0), _unsw_frame(20, 1)
    test.loc[0, "proto"] = "sctp"  # never seen in training
    a, b = netflow.unsw_features(train, test)
    assert "label" not in a and "attack_cat" not in a and b.loc[0, "proto"] == -1
    a_nt, _ = netflow.unsw_features(train, test, drop_ttl=True)
    assert not set(netflow.UNSW_TTL) & set(a_nt.columns)


def test_cic_reads_days_labels_and_strips_column_names(tmp_path):
    for day, label in (("Monday-WorkingHours", "BENIGN"), ("Friday-WorkingHours-Afternoon-DDos", "DDoS")):
        pd.DataFrame({" Destination Port": [80, 443], " Flow Bytes/s": [1.0, float("inf")], " Label": ["BENIGN", label]}) \
            .to_csv(tmp_path / f"{day}.pcap_ISCX.csv", index=False)
    data = netflow.cic(tmp_path)
    assert set(data["day"]) == {"Monday", "Friday"}
    assert data["label"].tolist() == [0, 0, 0, 1]
    assert netflow.cic_features(data) == ["Destination Port", "Flow Bytes/s"]
    assert data["Flow Bytes/s"].isna().sum() == 2  # infinities become missing


def test_the_validation_slice_is_deterministic_and_about_a_fifth():
    mask = validation_mask(5000, "x")
    assert (mask == validation_mask(5000, "x")).all() and 0.15 < mask.mean() < 0.25


def test_threshold_separates_clean_scores():
    y = np.array([0] * 80 + [1] * 20)
    scores = np.concatenate([np.linspace(0, 0.3, 80), np.linspace(0.7, 1, 20)])
    t = threshold(y, scores)
    assert ((scores >= t).astype(int) == y).all()


def test_per_family_reports_recall_and_whether_training_saw_it():
    families = pd.Series(["BENIGN", "BENIGN", "DDoS", "DDoS", "Bot"])
    flags = {"m": np.array([0, 1, 1, 1, 0])}
    out = per_family(families, flags, seen={"BENIGN", "Bot"})
    assert out["DDoS"] == {"n": 2, "attack": True, "seen_in_training": False, "m": 1.0}
    assert out["BENIGN"]["m"] == 0.5 and out["BENIGN"]["attack"] is False
    assert out["Bot"]["seen_in_training"] is True


def test_both_pipelines_and_the_report_run_end_to_end(tmp_path, capsys):
    import json

    from sati.netdetect import report
    from sati.netdetect.run import run_cic, run_unsw

    unsw_dir, cic_dir = tmp_path / "unsw", tmp_path / "cic"
    unsw_dir.mkdir()
    cic_dir.mkdir()
    _unsw_frame(1500, 0).to_csv(unsw_dir / "UNSW_NB15_training-set.csv", index=False)
    _unsw_frame(600, 1).to_csv(unsw_dir / "UNSW_NB15_testing-set.csv", index=False)
    rng = np.random.default_rng(2)
    for day, family in (("Monday-WorkingHours", "BENIGN"), ("Tuesday-WorkingHours", "SSH-Patator"),
                        ("Wednesday-workingHours", "DoS Hulk"), ("Friday-WorkingHours-Afternoon-DDos", "DDoS")):
        n = 800
        attack = rng.random(n) < (0 if family == "BENIGN" else 0.3)
        pd.DataFrame({" Destination Port": rng.integers(1, 9000, n), " Flow Duration": rng.random(n) + attack * 3,
                      " Label": np.where(attack, family, "BENIGN")}).to_csv(cic_dir / f"{day}.pcap_ISCX.csv", index=False)

    results = {"model": "sati-chandraghanta-v0", "weights_note": "n/a",
               "datasets": {"unsw": run_unsw(unsw_dir), "cic": run_cic(cic_dir)}}
    assert results["datasets"]["unsw"]["detectors"]["chandraghanta-v0"]["f1"] > 0.9  # TTL gives it away
    assert results["datasets"]["cic"]["per_family"]["DDoS"]["seen_in_training"] is False
    assert "chandraghanta-v1 (either)" in results["datasets"]["cic"]["detectors"]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results), encoding="utf-8")
    assert report.main(str(path)) == 0
    assert "random split (reference)" in capsys.readouterr().out


def test_v3_fusion_weight_is_chosen_on_families_held_out_of_training(monkeypatch):
    import numpy as np
    import pandas as pd

    from sati.netdetect import run

    monkeypatch.setattr(run, "ROUNDS", 20)
    rng = np.random.default_rng(0)
    x = pd.DataFrame(rng.normal(size=(2000, 4)), columns=list("abcd"))
    fam = np.array(["BENIGN"] * 2000, dtype=object)
    y = np.zeros(2000, int)
    fam[:200], y[:200] = "A", 1
    x.loc[:199, "a"] += 4
    fam[200:400], y[200:400] = "B", 1
    x.loc[200:399, "b"] += 4
    flags, info = run.fused_unseen(x, y, pd.Series(fam), x.iloc[:50], "t")
    assert info["held_out_families"] == ["A", "B"]
    assert info["weight"] in run.WEIGHTS and set(info["mean_held_out_recall"]) == {str(w) for w in run.WEIGHTS}
    assert flags.shape == (50,) and set(np.unique(flags)) <= {0, 1}


def test_nslkdd_reads_the_official_files_and_codes_categories_from_training_only(tmp_path):
    from sati.sources import netflow

    def row(service: str, attack: str) -> str:
        values = ["0", "tcp", service, "SF"] + ["1"] * 37 + [attack, "20"]
        return ",".join(values)

    (tmp_path / "KDDTrain+.txt").write_text("\n".join([row("http", "normal"), row("ftp", "neptune")]) + "\n")
    (tmp_path / "KDDTest+.txt").write_text("\n".join([row("http", "normal"), row("smtp", "mailbomb")]) + "\n")
    data = netflow.nslkdd(tmp_path)
    assert data["train"]["label"].tolist() == [0, 1] and data["test"]["family"].tolist() == ["normal", "mailbomb"]
    a, b = netflow.nslkdd_features(data["train"], data["test"])
    assert list(a.columns) == [c for c in netflow.NSLKDD_COLUMNS if c not in ("attack", "difficulty")]
    assert b["service"].tolist()[1] == -1  # 'smtp' never seen in training
