"""R80: the export route serves a document that leaves, and survives leaving.

The route's job is the part `packages/core` cannot do — reach the ledger — so
these tests are about provenance reaching the file and about the response being
shaped like a download rather than a page.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _incident_id(client) -> str:
    incidents = client.get("/api/v1/incidents").json()
    if not incidents:
        pytest.skip("no incidents are seeded in this configuration")
    return incidents[0]["id"]


def test_the_export_is_served_as_a_download(client):
    """`text/markdown` with a filename, so a browser saves it. A document that
    renders in the tab is a page, and the task was a file that leaves."""
    incident = _incident_id(client)
    response = client.get(f"/api/v1/incidents/{incident}/draft/post_incident/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert incident in disposition and "draft" in disposition


def test_the_audit_trail_reaches_the_file(client):
    """The route's whole reason to exist: core has no store, so provenance can
    only be attached here. Checked against an independent read of /audit."""
    incident = _incident_id(client)
    document = client.get(
        f"/api/v1/incidents/{incident}/draft/post_incident/export"
    ).text
    records = client.get(f"/api/v1/audit?incident_ref={incident}&limit=200").json()
    if not records:
        pytest.skip("this incident has no audit records in this configuration")

    for record in records[:5]:
        assert record["summary"] in document, "an audit record did not reach the export"
        assert record["kind"] in document
    assert "Provenance" in document


def test_every_cited_reference_survives_the_render(client):
    """The guarantee the on-screen draft has, held across the conversion — the
    thing a format change most reliably loses."""
    incident = _incident_id(client)
    on_screen = client.get(f"/api/v1/incidents/{incident}/draft/post_incident").json()
    document = client.get(
        f"/api/v1/incidents/{incident}/draft/post_incident/export"
    ).text

    for section in on_screen["sections"]:
        for line in section["lines"]:
            assert line["text"] in document
            for ref in line["refs"]:
                assert f"`{ref}`" in document


def test_it_is_a_draft_on_its_face(client):
    """A file in a shared folder has lost the interface that said 'draft' on
    the reader's behalf, so the document has to carry it."""
    incident = _incident_id(client)
    document = client.get(
        f"/api/v1/incidents/{incident}/draft/post_incident/export"
    ).text

    assert document.startswith("#")
    # Case-insensitively: both of R70's titles already begin with "Draft", and
    # the marker is appended only when a title would otherwise lack it.
    assert "draft" in document.splitlines()[0].lower()
    assert "has been adopted, approved or signed off" in document
    assert "adopt_report" in document


def test_it_names_where_and_when_it_came_from(client):
    incident = _incident_id(client)
    document = client.get(
        f"/api/v1/incidents/{incident}/draft/post_incident/export"
    ).text

    assert "**Generated:**" in document
    assert f"/incidents/{incident}/draft/post_incident/export" in document
    assert "Exported documents do not update" in document


def test_an_unknown_incident_is_404_not_an_empty_report(client):
    """The failure that would matter: a blank but well-formed report for an
    incident that does not exist reads as an incident with nothing in it."""
    response = client.get("/api/v1/incidents/INC-0000-0000/draft/post_incident/export")
    assert response.status_code == 404


def test_an_unknown_kind_is_404(client):
    incident = _incident_id(client)
    response = client.get(f"/api/v1/incidents/{incident}/draft/not_a_document/export")
    assert response.status_code == 404


def test_the_playbook_exports_too(client):
    """Both documents R70 built, not only the report."""
    incident = _incident_id(client)
    response = client.get(f"/api/v1/incidents/{incident}/draft/playbook/export")
    assert response.status_code == 200
    assert "adopt_playbook" in response.text
