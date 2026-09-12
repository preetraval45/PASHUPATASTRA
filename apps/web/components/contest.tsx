import Link from "next/link";

import { Badge, Panel } from "@/components/ui";
import { hrefFor } from "@/lib/refs";
import type { Contest, ContestCase } from "@/lib/api";

/**
 * The plausible-and-wrong explanation, argued and then answered.
 *
 * The Blue Team rubric tells a player that one of the explanations is plausible
 * and wrong and scores them on opening the evidence that rules it out. This is
 * the same standard applied to the console's own diagnosis, on the same
 * incidents — which is what makes the rubric a demonstrated claim rather than a
 * scoring note on a game page.
 *
 * **The alternative is given its case first, in its own words.** A panel that
 * led with the rejection would be reporting a conclusion and calling it a
 * challenge. What a reader needs to see is the version of events that would
 * have been believed, and then what closed it.
 *
 * **`unrefuted` is not the alternative winning the argument** — it is the
 * diagnosis not having won it, which is an open question rather than a rival
 * conclusion. The distinction is easy to lose in a badge, so the panel says it
 * in a sentence rather than relying on the word.
 *
 * The confidence figures are shown and explicitly do not decide. Showing them
 * without that sentence would invite exactly the reading the module refuses:
 * that 0.86 against 0.09 is itself the refutation.
 */
export function ContestPanel({ contest }: { contest: Contest }) {
  const upheld = contest.verdict === "upheld";

  return (
    <Panel
      title="The plausible and wrong explanation"
      aside={
        <Badge status={upheld ? "neutral" : "warning"}>
          {upheld ? "ruled out" : "not ruled out"}
        </Badge>
      }
    >
      <div className="space-y-6">
        <section>
          <h3 className="label">The case for it</h3>
          <p className="mt-2 text-sm leading-relaxed">{contest.rival.statement}</p>
          <p className="mt-2 text-sm text-[rgb(var(--muted))]">
            It explains{" "}
            <Refs refs={contest.shared} incidentRef={contest.incident_ref} /> — the same
            observation{contest.shared.length === 1 ? "" : "s"} the diagnosis rests on.
            {contest.unexplained_by_leader.length > 0 && (
              <>
                {" "}
                It also accounts for{" "}
                <Refs
                  refs={contest.unexplained_by_leader}
                  incidentRef={contest.incident_ref}
                />
                , which the diagnosis does not cite.
              </>
            )}
          </p>
        </section>

        <section>
          <h3 className="label">{upheld ? "What rules it out" : "What does not rule it out"}</h3>
          {upheld ? (
            <p className="mt-2 text-sm leading-relaxed">
              <Refs refs={contest.ruled_out_by} incidentRef={contest.incident_ref} />.
              The diagnosis stands: {contest.leader.statement}
            </p>
          ) : (
            <p className="mt-2 text-sm leading-relaxed">
              Nothing stored does. The diagnosis leads it only on confidence, and a
              confidence figure is a number an author wrote rather than a record anyone
              can check —{" "}
              <strong className="text-[rgb(var(--fore))]">
                so this alternative has not been beaten, it has been ranked below.
              </strong>{" "}
              That makes it an open question, not a reason to prefer it.
            </p>
          )}
          {contest.unresolved_rejection.length > 0 && (
            <p className="mt-2 text-sm text-[rgb(var(--muted))]">
              {contest.unresolved_rejection.length} claimed contradiction
              {contest.unresolved_rejection.length === 1 ? "" : "s"} (
              <span className="mono">{contest.unresolved_rejection.join(", ")}</span>)
              resolve to nothing and are not counted.
            </p>
          )}
        </section>

        <section>
          <h3 className="label">Where each rests</h3>
          <div className="mt-2 space-y-3">
            <Side label="Diagnosis" side={contest.leader} incidentRef={contest.incident_ref} />
            <Side label="Alternative" side={contest.rival} incidentRef={contest.incident_ref} />
          </div>
          <p className="mt-3 text-xs text-[rgb(var(--faint))]">
            Confidence is shown and does not decide the verdict. The alternative is beaten
            only where something stored contradicts it.
          </p>
        </section>
      </div>
    </Panel>
  );
}

function Side({
  label,
  side,
  incidentRef,
}: {
  label: string;
  side: ContestCase;
  incidentRef: string;
}) {
  return (
    <div className="min-w-0">
      <p className="text-sm">
        <span className="label mr-2">{label}</span>
        <span className="mono text-xs text-[rgb(var(--faint))]">
          confidence {side.confidence.toFixed(2)}
        </span>
      </p>
      <p className="mt-1 text-sm text-[rgb(var(--muted))] break-words">
        rests on <Refs refs={side.supported_by} incidentRef={incidentRef} />
        {side.uncited.length > 0 && (
          <>
            {" "}
            and claims <span className="mono">{side.uncited.join(", ")}</span>, which
            resolve{side.uncited.length === 1 ? "s" : ""} to nothing
          </>
        )}
      </p>
    </div>
  );
}

function Refs({ refs, incidentRef }: { refs: string[]; incidentRef: string }) {
  if (refs.length === 0) return <span className="mono">nothing</span>;
  return (
    <span className="mono">
      {refs.map((ref, at) => (
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
  );
}
