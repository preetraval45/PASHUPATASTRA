import Link from "next/link";

import { Badge, Ident, Panel } from "@/components/ui";
import { hrefFor } from "@/lib/refs";
import { tierLabel, type Draft, type Verdict } from "@/lib/api";

/**
 * A drafted playbook or post-incident report, and what adopting it would cost.
 *
 * **Labelled a draft in the panel title, in a badge, and in the document's own
 * title.** Three times is not redundancy here: this is a document written to be
 * copied out of a browser, and the failure it must not have is a paragraph
 * arriving somewhere else with the word "draft" left behind on the page it came
 * from. The heading a reader copies is the one that carries it.
 *
 * **Every line shows its refs as links**, because a draft's whole claim is that
 * a reviewer can check it faster than they could write it. A sentence without a
 * ref cannot occur — `drafts.Line` refuses to construct one — so a line here
 * with nothing beside it would be a rendering bug, not an uncited assertion.
 *
 * There is no adopt button. Adopting is a registered action that Dharma scores
 * and a human authorises, so what this shows is the verdict for that action:
 * what it would need, from whom. A button that implied one click would finish
 * it would be the lie the whole task is named against.
 */
export function DraftPanel({
  draft,
  verdict,
}: {
  draft: Draft;
  verdict?: Verdict | null;
}) {
  return (
    <Panel
      title={draft.title}
      aside={<Badge status="neutral">draft — not adopted</Badge>}
    >
      <div className="space-y-6">
        {draft.sections.map((section) => (
          <section key={section.title}>
            <h3 className="label">{section.title}</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {section.lines.map((line, index) => (
                <li key={`${section.title}-${index}`} className="min-w-0">
                  <span className="break-words">{line.text}</span>{" "}
                  <span className="mono whitespace-nowrap text-xs text-[rgb(var(--faint))]">
                    {line.refs.map((ref, at) => (
                      <span key={ref}>
                        {at > 0 && ", "}
                        <Link
                          href={hrefFor(ref, draft.incident_ref)}
                          className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                        >
                          {label(ref, draft.incident_ref)}
                        </Link>
                      </span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <div className="mt-6 border-t border-[rgb(var(--edge))] pt-4 text-sm">
        <p className="text-[rgb(var(--muted))]">
          Adopting this is <Ident>{draft.adopt_action_id}</Ident>
          {verdict ? (
            <>
              {" "}
              — scored {verdict.effective_risk}, {tierLabel(verdict.tier).toLowerCase()}
              {verdict.required_approvers.length > 0 && (
                <>
                  {" "}
                  by <span className="mono">{verdict.required_approvers.join(", ")}</span>
                </>
              )}
              .
            </>
          ) : (
            <>, a registered action the policy engine scores before anyone accepts it.</>
          )}
        </p>
        <p className="mt-2 text-xs text-[rgb(var(--faint))]">
          Nothing here has been adopted. This document is assembled from the incident
          each time it is asked for, so it cannot go stale against the incident it
          describes — and it cannot be saved into something that stops saying draft.
        </p>
      </div>
    </Panel>
  );
}

/** The same shortening the chat citations use: the incident prefix is identical
 *  on every ref in a document about one incident, so it carries no information
 *  and costs a line of width. */
function label(ref: string, incidentId: string): string {
  return ref.startsWith(`${incidentId}#`) ? ref.slice(incidentId.length + 1) : ref;
}
