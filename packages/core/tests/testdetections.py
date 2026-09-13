"""R77: every hand-written rule names its author and its incident, parses as
Sigma, and cannot be admitted without either."""

from __future__ import annotations

import pytest

from pashupatastra.detections import DetectionsError, load_rules, parse_rule

MINIMAL = """
title: A rule
id: 11111111-2222-5333-8444-555555555555
author: Someone
x-incidents: [INC-2026-0903]
logsource: {category: process_creation, product: windows}
detection:
  selection: {Image|endswith: '\\thing.exe'}
  condition: selection
level: low
tags: [attack.t1053.005]
"""


def test_the_committed_library_loads_and_every_rule_is_signed_and_tied() -> None:
    rules = load_rules()
    assert rules, "the library is empty"
    for rule in rules:
        assert rule.author and rule.author != "sati"
        assert rule.incidents
        assert rule.technique_id
        assert rule.valid, rule.problems


def test_every_committed_rule_parses_under_pysigma() -> None:
    pysigma = pytest.importorskip("sigma.rule", reason="pysigma is a dev dependency")
    for rule in load_rules():
        parsed = pysigma.SigmaRule.from_yaml(rule.text)
        assert parsed.title == rule.title


def test_a_rule_without_an_author_is_refused_not_loaded_blank() -> None:
    with pytest.raises(DetectionsError, match="author"):
        parse_rule(MINIMAL.replace("author: Someone\n", ""))


def test_a_rule_tied_to_no_incident_is_refused() -> None:
    with pytest.raises(DetectionsError, match="x-incidents"):
        parse_rule(MINIMAL.replace("x-incidents: [INC-2026-0903]\n", "x-incidents: []\n"))


def test_the_technique_comes_from_the_standard_attack_tag() -> None:
    rule = parse_rule(MINIMAL)
    assert rule.technique_id == "T1053.005"
    assert parse_rule(MINIMAL.replace("tags: [attack.t1053.005]", "tags: [attack.persistence]")).technique_id is None


def test_two_files_with_one_id_are_refused(tmp_path) -> None:
    (tmp_path / "a.yml").write_text(MINIMAL, encoding="utf-8")
    (tmp_path / "b.yml").write_text(MINIMAL, encoding="utf-8")
    with pytest.raises(DetectionsError, match="twice"):
        load_rules(tmp_path)
