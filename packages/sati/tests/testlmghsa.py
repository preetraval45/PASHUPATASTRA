"""Kushmanda v3's GitHub advisories: only GHSA records with real text, CVE aliases kept."""

from __future__ import annotations

from sati.lm.corpus import ghsa_record

DETAILS = "When parsing JSON there is no limit to the depth of the stack, so deeply nested input " * 3


def test_a_ghsa_record_becomes_a_document_with_its_cve_alias():
    doc = ghsa_record({"id": "GHSA-aaaa-bbbb-cccc", "summary": "Stack overflow", "details": DETAILS,
                       "aliases": ["CVE-2024-0001", "RUSTSEC-2024-1"]})
    assert doc["source"] == "github-advisory"
    assert doc["text"].startswith("GHSA-aaaa-bbbb-cccc (CVE-2024-0001): Stack overflow\n")


def test_other_sources_withdrawn_and_thin_records_are_dropped():
    assert ghsa_record({"id": "PYSEC-2024-1", "details": DETAILS}) is None  # another licence
    assert ghsa_record({"id": "GHSA-x", "details": DETAILS, "withdrawn": "2024-01-01"}) is None
    assert ghsa_record({"id": "GHSA-x", "details": "too short"}) is None
