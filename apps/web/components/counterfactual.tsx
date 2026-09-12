import Link from "next/link";

import { Badge, Ident, Panel } from "@/components/ui";
import { hrefFor } from "@/lib/refs";
import type { Counterfactual, TimelineStep } from "@/lib/api";

/**
 * What acting at the first defensible moment would have prevented, and what it
 * would not.
 *
 * **Both columns, always.** The prevented steps are the interesting number and
 * the unavoidable ones are what stop it being a boast: a step that came later
 * but never depended on the thing removed would have happened anyway, and a
 * panel showing only the winnings is an advertisement. They are rendered with
 * equal weight for that reason, not tucked behind a disclosure — R68 made the
 * same argument about putting doubt one click further away than the conclusion.
 *
 * **The basis is rendered, not summarised.** Two of its lines are assumptions
 * the records cannot settle — that the block would have worked immediately, and
 * that the attacker would not simply have taken another route — and they are
 * the first things a retelling drops. They are the difference between an
 * estimate and a claim, so they sit under the number rather than in a tooltip.
 *
 * There is no control to pick a different moment. The one the records support
 * is the earliest they would have justified acting, which is the question the
 * homepage's cost-of-the-gap framing is actually about; a free-form time picker
 * would mostly produce refusals a reader would read as the feature being broken.
 */
export function CounterfactualPanel({ result }: { result: Counterfactual }) {
  const minutes = Math.round(result.gap_seconds / 60);

  return (
    <Panel
      title="If we had acted sooner"
      aside={<Badge status="neutral">estimate</Badge>}
    >
      <div className="space-y-6">
        <p className="text-sm text-[rgb(var(--muted))]">
          Acting on <Ident>{result.entity_key}</Ident> at{" "}
          <span className="mono">{time(result.at)}</span> — the first moment the
          records would have justified it — would have pre-empted{" "}
          <strong className="text-[rgb(var(--fore))]">
            {result.prevented.length} recorded step
            {result.prevented.length === 1 ? "" : "s"}
          </strong>
          {minutes > 0 && <> over the following {minutes} minutes</>}.
        </p>

        {result.prevented.length > 0 && (
          <StepList
            title="What would not have happened"
            steps={result.prevented}
            incidentRef={result.incident_ref}
          />
        )}

        {/* The half that keeps this honest. */}
        {result.unavoidable.length > 0 && (
          <StepList
            title="What would have happened anyway"
            note="Later than the intervention, but not downstream of it."
            steps={result.unavoidable}
            incidentRef={result.incident_ref}
          />
        )}

        {result.untimed.length > 0 && (
          <section>
            <h3 className="label">Steps that could not be placed in time</h3>
            <ul className="mt-2 space-y-2 text-sm text-[rgb(var(--muted))]">
              {result.untimed.map((step) => (
                <li key={step.index} className="min-w-0 break-words">
                  <span className="mono text-[rgb(var(--astra))]">{step.entity_key}</span>{" "}
                  {step.reason}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="label">What this estimate rests on</h3>
          <ul className="mt-2 space-y-2 text-sm text-[rgb(var(--muted))]">
            {result.basis.map((line) => (
              <li key={line} className="min-w-0 break-words">
                {line}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="mt-6 border-t border-[rgb(var(--edge))] pt-4 text-xs text-[rgb(var(--faint))]">
        <p>
          Derived from this incident&rsquo;s stored timeline and the access edges between
          its entities, both of which cite their own evidence. It is an estimate, not a
          measurement: nothing recorded here says what the intruder would have done next.
        </p>
      </div>
    </Panel>
  );
}

function StepList({
  title,
  note,
  steps,
  incidentRef,
}: {
  title: string;
  note?: string;
  steps: TimelineStep[];
  incidentRef: string;
}) {
  return (
    <section>
      <h3 className="label">{title}</h3>
      {note && <p className="mt-1 text-xs text-[rgb(var(--faint))]">{note}</p>}
      <ul className="mt-2 space-y-2 text-sm">
        {steps.map((step) => (
          <li key={step.index} className="min-w-0">
            <span className="mono text-xs text-[rgb(var(--faint))]">{time(step.at)}</span>{" "}
            <span className="mono break-all text-[rgb(var(--astra))]">{step.entity_key}</span>{" "}
            <span className="break-words">{step.transition}</span>{" "}
            <span className="mono whitespace-nowrap text-xs text-[rgb(var(--faint))]">
              {step.refs.map((ref, at) => (
                <span key={ref}>
                  {at > 0 && ", "}
                  <Link
                    href={hrefFor(ref, incidentRef)}
                    className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                  >
                    {ref}
                  </Link>
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Times are rendered in UTC deliberately. A server-rendered local time and the
 *  browser's local time disagree, and on a page whose argument is a sequence of
 *  moments that disagreement is the one thing a reader would notice. */
function time(iso: string): string {
  return new Date(iso).toISOString().slice(11, 16) + "Z";
}
