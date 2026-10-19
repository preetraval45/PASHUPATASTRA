"""Kushmanda's data pipeline — cleaning, near-duplicate removal, instruction data."""

from __future__ import annotations

from sati.lm import clean, sft

LONG = (
    "Adversaries may send phishing messages to gain access to victim systems. "
    "All forms of phishing are electronically delivered social engineering, and "
    "they can be targeted at a specific individual, company or industry."
)


def test_normalise_strips_links_citations_and_markup():
    text = "[Shamoon](https://x) wipes disks.(Citation: Unit 42) <code>rm</code>"
    assert clean.normalise(text) == "Shamoon wipes disks. rm"


def test_short_or_non_text_documents_are_filtered():
    assert not clean.keep("too short")
    assert not clean.keep("0x41 0x42 " * 20)
    assert clean.keep(LONG)


def test_exact_and_near_duplicates_are_removed_but_distinct_text_kept():
    # The same paragraph with trailing boilerplate: the kind of copy that
    # repeats across feeds. (One changed word in a 40-word paragraph is NOT a
    # near-duplicate — its true shingle similarity is ~0.70.)
    near = LONG + " Read more."
    other = ("Ransomware encrypts files on local and network drives and leaves a note demanding "
             "payment for the decryption key; backups that are offline survive it.")
    docs = [{"text": LONG}, {"text": LONG}, {"text": near}, {"text": other}]
    kept, stats = clean.deduplicate(docs)
    assert stats["exact_duplicates"] == 1 and stats["near_duplicates"] == 1
    assert [d["text"] for d in kept] == [clean.normalise(LONG), clean.normalise(other)]


def test_minhash_estimates_similarity():
    a, b = clean.signature(LONG), clean.signature(LONG.upper())
    assert clean.jaccard_estimate(a, b) == 1.0
    assert clean.jaccard_estimate(a, clean.signature("completely different words entirely here now")) < 0.2


def test_instruction_pairs_are_held_out_by_entity():
    entities = [f"T{1000 + i}" for i in range(2000)]
    held = [e for e in entities if sft.held_out(e)]
    assert 100 <= len(held) <= 300
    assert all(sft.held_out(e) for e in held)  # stable


def test_the_chat_template_separates_question_from_answer():
    prompt, answer = sft.format_pair("What is T1566?", "T1566 is Phishing.")
    assert prompt.startswith(sft.USER) and prompt.rstrip().endswith(sft.ASSISTANT)
    assert answer.endswith(sft.END)
