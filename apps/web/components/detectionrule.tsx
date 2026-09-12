import Link from "next/link";

import { Badge, Ident, Panel } from "@/components/ui";
import { hrefFor } from "@/lib/refs";
import type { DetectionRule } from "@/lib/api";

/**
 * A Sigma rule drafted from one step of this incident, and the account of what
 * its telemetry could not supply.
 *
 * **The mapping table is the panel, not a footnote to it.** A rule shown alone
 * asks to be believed; the interesting question a reviewer has is "where did
 * `Computer` come from", and answering it beside every field is the difference
 * between a rule you can check and one you can only admire. Each row names the
 * telemetry field and links the events it was read from.
 *
 * **The caveats are rendered from the rule, and also live inside the YAML.**
 * Duplication on purpose: this block does not travel. The reader who matters
 * most is the one who copies the rule into a detection repository, and by then
 * this panel is a browser tab they closed — so `sigma.py` writes the gaps and
 * the warning into the document as well. What is on screen here is the same
 * text, not a friendlier summary of it, because two accounts of the same
 * limitation is how they come to disagree.
 *
 * There is no deploy button and no download. This is `status: experimental`
 * assembled from one incident by a console that has never seen the log pipeline
 * it would run against, and a control implying otherwise would be the claim the
 * whole module is arranged against.
 */
export function DetectionRulePanel({ rule }: { rule: DetectionRule }) {
  return (
    <Panel
      title={rule.title}
      aside={
        <div className="flex flex-wrap items-center gap-2">
          <Badge status={rule.valid ? "neutral" : "critical"}>
            {rule.valid ? "parses as sigma" : "does not parse"}
          </Badge>
          <Badge status={rule.behavioural ? "neutral" : "warning"}>
            {rule.behavioural ? "generalises" : "indicator match"}
          </Badge>
        </div>
      }
    >
      <div className="space-y-6">
        {rule.technique && (
          <p className="text-sm text-[rgb(var(--muted))]">
            Drafted for <Ident>{rule.technique.id}</Ident> {rule.technique.name} (
            {rule.technique.tactic}), from the events this incident&rsquo;s causal step
            cites.
          </p>
        )}

        {/* The clause R71 is measured on: every field names where it came from. */}
        <section>
          <h3 className="label">Telemetry field to rule field</h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[34rem] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-[rgb(var(--faint))]">
                  <th className="py-1 pr-4 font-normal">Sigma field</th>
                  <th className="py-1 pr-4 font-normal">Read from</th>
                  <th className="py-1 pr-4 font-normal">Value</th>
                  <th className="py-1 font-normal">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {rule.mappings.map((mapping) => (
                  <tr
                    key={mapping.sigma_field}
                    className="border-t border-[rgb(var(--edge))] align-top"
                  >
                    <td className="py-2 pr-4">
                      <span className="mono break-all">{mapping.sigma_field}</span>
                      {!mapping.generalises && (
                        <span className="ml-2 whitespace-nowrap text-xs text-[rgb(var(--faint))]">
                          this incident only
                        </span>
                      )}
                    </td>
                    <td className="mono py-2 pr-4 break-all text-xs text-[rgb(var(--muted))]">
                      {mapping.source_field}
                    </td>
                    <td className="mono py-2 pr-4 break-all text-xs">{mapping.value}</td>
                    <td className="mono py-2 text-xs">
                      {mapping.refs.map((ref, at) => (
                        <span key={ref}>
                          {at > 0 && ", "}
                          <Link
                            href={hrefFor(ref, rule.incident_ref)}
                            className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                          >
                            {ref}
                          </Link>
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {rule.gaps.length > 0 && (
          <section>
            <h3 className="label">What this telemetry could not supply</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {rule.gaps.map((gap) => (
                <li key={gap.sigma_field} className="min-w-0">
                  <span className="mono break-all text-[rgb(var(--astra))]">
                    {gap.sigma_field}
                  </span>{" "}
                  <span className="break-words text-[rgb(var(--muted))]">{gap.reason}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {rule.not_mapped.length > 0 && (
          <section>
            <h3 className="label">Held, and deliberately not mapped</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {rule.not_mapped.map((gap) => (
                <li key={`${gap.sigma_field}-${gap.reason.slice(0, 24)}`} className="min-w-0">
                  <span className="mono break-all text-[rgb(var(--astra))]">
                    {gap.sigma_field}
                  </span>{" "}
                  <span className="break-words text-[rgb(var(--muted))]">{gap.reason}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="label">The rule</h3>
          <pre className="mt-2 overflow-x-auto rounded border border-[rgb(var(--edge))] bg-[rgb(var(--sunk))] p-3 text-xs leading-relaxed">
            <code className="mono">{rule.yaml}</code>
          </pre>
        </section>

        {!rule.valid && (
          <ul className="space-y-1 text-sm text-[rgb(var(--critical))]">
            {rule.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-6 border-t border-[rgb(var(--edge))] pt-4 text-xs text-[rgb(var(--faint))]">
        <p>
          Drafted from stored telemetry, never deployed and never adopted. Every field
          above was read from an event this incident cites; nothing was written from what
          a model knows about Sigma.
        </p>
      </div>
    </Panel>
  );
}
