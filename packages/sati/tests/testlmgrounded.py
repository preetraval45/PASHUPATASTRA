"""Kushmanda v2 — grounded instruction data, its scoring, and the NVD corpus parser."""

from __future__ import annotations

import random

from sati.lm import evaluate, sft
from sati.lm.corpus import nvd_record


def _pairs(n: int = 40) -> list[dict]:
    return [
        {"entity": f"T{1000 + i}", "pool": "technique", "kind": "lookup", "passage": f"T{1000 + i} Technique {i}: does thing {i}.",
         "q": f"Which ATT&CK technique ID is 'Technique {i}'?", "a": f"T{1000 + i}"}
        for i in range(n)
    ]


def test_every_answerable_context_holds_the_answer_at_the_cited_position():
    grounded = sft.ground(_pairs())
    answerable = [p for p in grounded if p["answerable"]]
    assert answerable
    for p in answerable:
        assert len(p["context"]) == sft.PASSAGES
        assert p["context"][p["cite"] - 1] == p["passage"]
        assert p["a"].endswith(f"[{p['cite']}]")


def test_unanswerable_contexts_leave_the_answer_out_and_abstain():
    grounded = sft.ground(_pairs(400))
    unanswerable = [p for p in grounded if not p["answerable"]]
    assert 0.03 < len(unanswerable) / len(grounded) < 0.2
    for p in unanswerable:
        assert p["passage"] not in p["context"] and p["a"] == sft.ABSTAIN


def test_grounding_is_deterministic():
    assert sft.ground(_pairs()) == sft.ground(_pairs())


def test_the_context_is_numbered_inside_the_prompt():
    prompt, _ = sft.format_pair("Which?", "T1 [2]", ["alpha", "beta", "gamma"])
    assert "[1] alpha\n[2] beta\n[3] gamma\nQuestion: Which?" in prompt


def test_parse_reads_the_citation_and_abstention():
    assert evaluate.parse("T1566 — Phishing [2]") == ("T1566 — Phishing", 2, False)
    assert evaluate.parse(sft.ABSTAIN)[2] is True


def test_rouge_l_is_one_for_identical_text_and_zero_for_disjoint():
    assert evaluate.rouge_l("the cat sat", "the cat sat") == 1.0
    assert evaluate.rouge_l("the cat sat", "dogs run fast") == 0.0
    assert 0 < evaluate.rouge_l("the cat sat on the mat", "the cat lay on a mat") < 1


def test_copy_precision_separates_copied_from_invented_answers():
    context = ["Adversaries may send phishing messages to gain access to victim systems."]
    assert evaluate.copy_precision("send phishing messages to gain access", context) == 1.0
    assert evaluate.copy_precision("attackers bribe the night guard for keys", context) == 0.0


def test_score_rewards_the_right_answer_and_citation_only():
    pairs = [p for p in sft.ground(_pairs()) if p["answerable"]][:10]
    perfect = evaluate.score(pairs, [p["a"] for p in pairs])["lookup"]
    assert perfect["exact_match"] == perfect["cited_right_passage"] == 1.0 and perfect["false_abstention"] == 0.0
    wrong = evaluate.score(pairs, [sft.ABSTAIN for _ in pairs])["lookup"]
    assert wrong["exact_match"] == 0.0 and wrong["false_abstention"] == 1.0


def test_the_lexical_baseline_finds_a_passage_by_word_overlap():
    pair = {"q": "Which ATT&CK technique ID is 'Phishing'?", "kind": "lookup",
            "context": ["T1059 Command and Scripting Interpreter: runs commands.", "T1566 Phishing: sends messages."]}
    assert evaluate.lexical(pair) == "T1566 [2]"
    assert evaluate.chance(pair, random.Random(0)).endswith(("[1]", "[2]"))


def test_nvd_records_skip_rejected_and_carry_their_weakness():
    accepted = {"cve": {"id": "CVE-2024-0001", "vulnStatus": "Analyzed",
                        "descriptions": [{"lang": "en", "value": "A buffer overflow in Example Server 1.2 allows remote attackers to run code."}],
                        "weaknesses": [{"description": [{"lang": "en", "value": "CWE-787"}]}]}}
    rejected = {"cve": {"id": "CVE-2024-0002", "vulnStatus": "Rejected",
                        "descriptions": [{"lang": "en", "value": "** REJECT ** Do not use this candidate number at all, ever."}]}}
    doc = nvd_record(accepted)
    assert doc["id"] == "CVE-2024-0001" and doc["text"].endswith("Weakness: CWE-787.")
    assert nvd_record(rejected) is None
