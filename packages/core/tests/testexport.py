"""R80: an exported report is checkable by someone who cannot see this system.

The failure this guards against is not a crash. It is a document that looks
complete, reads as a finding, and quietly dropped the half that made it
checkable — which is exactly what a format conversion tends to lose, because
the thing it drops is the interface that was carrying the caveats.
"""

from __future__ import annotations

import pytest

from pashupatastra.drafts import POST_INCIDENT, build_draft
from testdrafts import an_incident
from pashupatastra.export import (
    DRAFT_NOTICE,
    STALENESS_NOTICE,
    filename,
    to_markdown,
)

AUDIT_IDS = ("aud-0001", "aud-0002", "aud-0003")


def _render(**kwargs):
    draft = build_draft(POST_INCIDENT, an_incident())
    options = {
        "generated_at": "2026-10-07T20:00:00+00:00",
        "source": "https://pashupatastra.vercel.app/incidents/INC-2026-0901",
        "audit_ids": AUDIT_IDS,
    }
    options.update(kwargs)
    return draft, to_markdown(draft, **options)


def test_every_assertion_keeps_its_evidence():
    """The one guarantee the on-screen version has that an export can lose."""
    draft, text = _render()
    for section in draft.sections:
        for line in section.lines:
            assert line.text in text, f"a line was dropped: {line.text[:40]!r}"
            for ref in line.refs:
                assert f"`{ref}`" in text, f"{ref} is cited on screen and not in the export"


def test_the_audit_ids_travel_with_it():
    """R80's actual addition. Evidence refs say which observations a sentence
    rests on; audit ids say which decisions were taken. A reader needs both to
    reconstruct the incident without a login."""
    _, text = _render()
    for record_id in AUDIT_IDS:
        assert f"`{record_id}`" in text


def test_no_audit_records_is_stated_rather_than_omitted():
    """An export with no provenance block and one whose incident recorded no
    decisions look identical on the page, and they are different facts — the
    same rule /impact is built on."""
    _, text = _render(audit_ids=())
    assert "No audit records were found" in text
    assert "Provenance" in text, "the section vanished instead of explaining itself"


def test_it_says_draft_where_a_conversion_cannot_strip_it():
    """Four places, because a document that reaches an inbox is read as a
    finding unless it argues otherwise on every screen."""
    draft, text = _render()
    # The marker appears once, not twice: both of R70's titles already begin
    # with "Draft", and "Draft ... — DRAFT" reads as an unchecked template.
    assert text.startswith(f"# {draft.title}")
    assert "draft" in text.splitlines()[0].lower()
    assert "— DRAFT" not in text.splitlines()[0]
    assert DRAFT_NOTICE in text
    for section in draft.sections:
        assert f"## {section.title} *(draft)*" in text
    assert "This file is not that." in text


def test_it_carries_its_origin_and_moment():
    """A document with no origin is one whose claims cannot be aged."""
    _, text = _render()
    assert "2026-10-07T20:00:00+00:00" in text
    assert "https://pashupatastra.vercel.app/incidents/INC-2026-0901" in text
    assert STALENESS_NOTICE in text


def test_adoption_names_a_registered_action():
    """Not a sentence saying someone may approve it — the action id the policy
    engine would actually score."""
    draft, text = _render()
    assert f"`{draft.adopt_action_id}`" in text
    assert draft.adopt_action_id == "adopt_report"


def test_the_filename_carries_the_context_the_folder_will_strip():
    draft = build_draft(POST_INCIDENT, an_incident())
    name = filename(draft)
    assert name.startswith("INC-")
    assert "draft" in name
    assert name.endswith(".md")
    # Nothing that would need escaping in a Content-Disposition header or on a
    # filesystem.
    assert all(c.isalnum() or c in "-_." for c in name)


def test_an_empty_section_says_so_instead_of_disappearing():
    """drafts.py keeps empty sections deliberately — 'nothing was verified' is
    a claim a reader can check and a missing heading is a lapse. The export
    must not undo that by rendering nothing."""
    from pashupatastra.drafts import Draft, Section

    draft = Draft(
        kind=POST_INCIDENT,
        incident_ref="INC-2026-0901",
        title="Post-incident report",
        sections=(Section(title="What was verified", lines=()),),
    )
    text = to_markdown(
        draft,
        generated_at="2026-10-07T20:00:00+00:00",
        source="test",
        audit_ids=AUDIT_IDS,
    )
    assert "## What was verified *(draft)*" in text
    assert "Nothing recorded under this heading." in text


def test_the_reference_count_matches_the_draft():
    """A count typed independently of the thing it counts drifts; this one is
    taken from the draft, and the test holds it to that."""
    draft, text = _render()
    assert f"{len(draft.refs)} distinct reference(s)" in text
    assert len(draft.refs) > 0


def test_a_draft_line_still_cannot_exist_without_refs():
    """The constructor rule R70 established, restated here because the export
    is the surface where dropping it would do the damage."""
    from pashupatastra.drafts import Line

    with pytest.raises(ValueError, match="cites nothing"):
        Line(text="The intrusion began on Tuesday.", refs=())
