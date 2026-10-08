"""A draft rendered to a file somebody can take away (R80).

R70 made the documents; this makes them portable. The difference is the whole
point of the task: a report read on the site sits next to the evidence it
cites, and one mailed to a regulator, pasted into a ticket or attached to a
post-mortem does not. So the exported form has to carry enough with it to be
checked **by someone who cannot see this system at all**.

That means three things the on-screen version gets for free:

* **Every assertion keeps its references.** `drafts.Line` already refuses to
  exist without them, so this cannot drop them — it renders what is there, and
  the test suite holds it to printing every one.
* **The audit record ids travel with it.** This is R80's actual addition.
  Evidence references say which observations a sentence rests on; audit ids say
  which decisions were taken, by what, and when. A reader holding both can
  reconstruct the incident against the ledger without being given a login. They
  are passed in rather than read here, because `packages/core` does not get to
  reach for a store.
* **It says where it came from and when.** A document with no origin is a
  document whose claims cannot be aged. Exports go stale: an incident reopens,
  a verification lands, an execution is rolled back, and a report printed
  before any of that is now wrong in a way nothing on its face reveals.

**It is still a draft, and says so in four places** — the title, a line under
it, the running header of every section, and the footer. Not decoration. A
draft that reaches a stakeholder's inbox is read as a finding unless the
document fights that on every screen, and the one thing a format conversion
reliably loses is the surrounding interface that said "draft" on the reader's
behalf.

Markdown rather than a binary format, and no PDF library. Markdown is readable
without any tool at all, survives being pasted anywhere, diffs, and converts to
PDF through the browser's own print path — which keeps a document generator out
of the dependency tree of a security product.
"""

from __future__ import annotations

from .drafts import Draft

#: Said on the document itself, not left to the covering email.
DRAFT_NOTICE = (
    "This is a draft assembled from stored records. Nothing in it has been "
    "adopted, approved or signed off by anyone. Adoption is a registered "
    "action that goes through policy evaluation and leaves its own audit "
    "record; if this document were adopted, that record — not this file — "
    "would be the evidence of it."
)

#: Why an export can be wrong while the system is right.
STALENESS_NOTICE = (
    "Exported documents do not update. An incident can reopen, a verification "
    "can land and an execution can be rolled back after this was written, and "
    "nothing on this page would show it. Check the references against the "
    "source before relying on it."
)


def to_markdown(
    draft: Draft,
    *,
    generated_at: str,
    source: str,
    audit_ids: tuple[str, ...] = (),
) -> str:
    """Render a draft as Markdown that can be checked away from this system.

    `audit_ids` are the ledger records for the incident, passed in by the
    caller: this module has no store and must not acquire one. An empty tuple
    is rendered as **an explicit statement that none were found**, never as an
    omitted section — a report that silently drops its provenance block reads
    exactly like one whose incident had no decisions recorded, and those are
    very different facts.
    """
    out: list[str] = []

    # The title already says "Draft" for both documents R70 builds, so this
    # appends the marker only when it would otherwise be missing — belt and
    # braces, not "Draft ... — DRAFT", which reads as a template nobody checked
    # and undermines the care the rest of the notice is asking the reader for.
    heading = draft.title if "draft" in draft.title.lower() else f"{draft.title} — DRAFT"
    out.append(f"# {heading}")
    out.append("")
    out.append(f"*{DRAFT_NOTICE}*")
    out.append("")
    out.append(f"- **Incident:** `{draft.incident_ref}`")
    out.append(f"- **Document:** {draft.kind} ({draft.status})")
    out.append(f"- **Generated:** {generated_at}")
    out.append(f"- **Source:** {source}")
    out.append("")

    for section in draft.sections:
        out.append(f"## {section.title} *(draft)*")
        out.append("")
        if not section.lines:
            # Kept rather than skipped, for the reason drafts.py states: an
            # empty section is a claim, and a missing one is a lapse.
            out.append("*Nothing recorded under this heading.*")
            out.append("")
            continue
        for line in section.lines:
            refs = ", ".join(f"`{ref}`" for ref in line.refs)
            out.append(f"- {line.text}")
            out.append(f"  - *evidence:* {refs}")
        out.append("")

    out.append("## Provenance")
    out.append("")
    out.append(
        f"Every assertion above cites the records it rests on; "
        f"{len(draft.refs)} distinct reference(s) in total."
    )
    out.append("")
    if audit_ids:
        out.append(
            "Audit records for this incident, against which the above can be "
            "reconstructed:"
        )
        out.append("")
        for record_id in audit_ids:
            out.append(f"- `{record_id}`")
    else:
        out.append(
            "**No audit records were found for this incident.** That is "
            "reported rather than omitted: an export with no provenance block "
            "and one whose incident has no recorded decisions look identical "
            "on the page, and they are not the same fact."
        )
    out.append("")
    out.append(f"*{STALENESS_NOTICE}*")
    out.append("")
    out.append(
        f"*Adopting this would require the registered action "
        f"`{draft.adopt_action_id}`, which is scored and routed through policy "
        f"evaluation like any other action. This file is not that.*"
    )
    out.append("")

    return "\n".join(out)


def filename(draft: Draft, *, extension: str = "md") -> str:
    """A filename that says what it is before anyone opens it.

    `draft` is in the name deliberately. A file called `INC-2026-0901-report.md`
    sitting in a shared folder six weeks later has lost every bit of context
    this module worked to attach, except whatever survives in its name.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in draft.incident_ref)
    return f"{safe}-{draft.kind}-draft.{extension}"
