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
