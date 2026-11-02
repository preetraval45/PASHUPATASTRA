"""Everyday security words point at the knowledge-base entry they mean (providers/concepts.py)."""

from __future__ import annotations

from app.engines.providers import concepts


def test_common_names_point_at_the_entry_they_mean():
    assert concepts.concept("What is ransomware?") == "T1486"
    assert concepts.concept("What is a DDoS attack?") == "T1498"
    assert concepts.concept("What is MFA?") == "M1032"
    # Hyphenated names survive: the framing filter would have split them.
    assert concepts.concept("What is a man-in-the-middle attack?") == "T1557"


def test_a_name_inside_a_longer_word_or_a_long_question_is_left_to_retrieval():
    assert concepts.concept("What is a dossier?") is None
    assert concepts.concept("Our ransomware playbook says to isolate hosts first but legal wants evidence kept, what now?") is None


def test_tactics_have_mitre_descriptions_and_real_technique_ids():
    name, tid, description, techniques = concepts.tactic("lateral movement")
    assert (name, tid) == ("Lateral Movement", "TA0008")
    assert description.startswith("The adversary is trying to")
    assert concepts.tactic("a lateral movement attack") == concepts.tactic("Lateral Movement")
    for _, tid, _, techniques in concepts.TACTICS.values():
        assert tid.startswith("TA") and len(techniques) == 3
        assert all(t.startswith("T1") for t in techniques)


def test_everyday_gaps_point_at_real_entries():
    # The launch-blocker gaps (2 Nov): each named term reaches the entry it means.
    assert concepts.concept("What is SQL injection?") == "CAPEC-66"
    assert concepts.concept("What is XSS?") == "CAPEC-63"
    assert concepts.concept("What is cryptojacking?") == "T1496"
    assert concepts.concept("What is vishing?") == "T1598.004"
    assert concepts.concept("What is least privilege?") == "M1026"


def test_terms_without_an_entry_get_nists_definition_and_its_link():
    title, definition, cited, url, related = concepts.glossary("What is a zero-day?")
    assert title == "Zero-day attack" and definition.startswith("An attack that exploits a previously unknown")
    assert url == "https://csrc.nist.gov/glossary/term/zero_day_attack" and cited == "CNSSI 4009-2022"
    assert concepts.glossary("what is a VPN")[0] == "Virtual private network (VPN)"
    assert concepts.glossary("Explain zero trust")[0] == "Zero trust"
    # Whole words only, and long questions stay with retrieval.
    assert concepts.glossary("What is a wormhole?") is None
    assert concepts.glossary("our VPN concentrator keeps dropping sessions after the last firmware update, why?") is None
    for _, definition, cited, url, _ in concepts.GLOSSARY.values():
        assert url.startswith("https://csrc.nist.gov/glossary/term/") and cited and definition.endswith(".")


def test_every_mapped_and_related_id_is_in_the_served_knowledge_base():
    # Rule 1: a name may only point at an entry that exists, so no answer is built on a missing passage.
    import json
    from pathlib import Path

    served = Path(__file__).resolve().parents[1] / "app" / "sati_models" / "knowledge.json"
    ids = {p["id"] for p in json.loads(served.read_text(encoding="utf-8"))}
    missing = {i for i in concepts.CONCEPTS.values() if i not in ids}
    missing |= {i for entry in concepts.GLOSSARY.values() for i in entry[4] if i not in ids}
    assert not missing, missing
