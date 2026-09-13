import type { Metadata } from "next";
import Link from "next/link";

import { Offline, Page, Panel } from "@/components/ui";
import { getAttackMatrix } from "@/lib/api";
import { hrefFor } from "@/lib/refs";

export const metadata: Metadata = {
  title: "ATT&CK coverage",
  description:
    "Which MITRE ATT&CK tactics and techniques the incident library has observed a step of, and which it has not — every cell linking to the step that fills it.",
};

export const dynamic = "force-dynamic";

/**
 * The matrix across the whole library (R75).
 *
 * A technique on one incident is a tag; the same tags across every incident
 * are a claim about coverage, and that is the one a reader cannot assemble by
 * opening incidents one at a time. Every filled cell links to the exact step
 * — `/incidents/{id}#chain-{n}` — not to a page, so the claim is checkable at
 * the place it was made.
 *
 * Empty columns stay on the board and read as *not observed*. "Not covered"
 * or "not detected" would claim something about a detection layer this
 * console does not run; an empty column is a fact about what the library's
 * three scenarios were written to show, and the page says so in words.
 *
 * Fourteen columns do not fit any phone, so above `sm` this is a scrolling
 * grid in ATT&CK's own column order and below it a stacked list of tactics —
 * one markup, one order, two layouts.
 */
export default async function AttackPage() {
  const matrix = await getAttackMatrix();
  if (matrix === null) return <Offline />;

  return (
    <Page
      title="ATT&CK coverage"
      description="What the incident library has observed a step of, tactic by tactic."
      actions={
        <p className="text-xs text-[rgb(var(--faint))]">
          <span className="tnum">{matrix.technique_count}</span> techniques ·{" "}
          <span className="tnum">{matrix.observed_tactics.length}</span> of{" "}
          <span className="tnum">{matrix.columns.filter((c) => c.known).length}</span> tactics
          observed · <span className="tnum">{matrix.incident_count}</span> incidents
        </p>
      }
    >
      <Panel title="The matrix" aside="in ATT&CK's own column order">
        <div className="min-w-0 max-w-full overflow-x-auto">
          <ol
            data-matrix
            className="sm:grid sm:grid-flow-col sm:auto-cols-[minmax(10rem,1fr)] sm:gap-3 space-y-4 sm:space-y-0"
          >
            {matrix.columns.map((column) => (
              <li
                key={column.tactic}
                data-tactic={column.tactic}
                data-observed={column.observed ? "" : undefined}
                className={`rounded-lg border p-3 ${
                  column.observed
                    ? "border-[rgb(var(--edge))]"
                    : "border-dashed border-[rgb(var(--edge))]/70"
                }`}
              >
                <h3 className="text-xs font-medium uppercase tracking-wide">
                  {column.tactic}
                  {!column.known && (
                    <span className="ml-1 text-[rgb(var(--warn))]" title="Not one of ATT&CK's fourteen tactics">
                      ?
                    </span>
                  )}
                </h3>
                {column.observed ? (
                  <ul className="mt-2 space-y-2">
                    {column.techniques.map((cell) => (
                      <li key={cell.id} data-technique={cell.id} className="text-sm">
                        <a
                          href={cell.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="focusable mono rounded text-xs underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                        >
                          {cell.id}
                        </a>
                        <p className="leading-snug">{cell.name}</p>
                        {/* One link per step, not per incident: the technique
                            was observed at a step, and that is where the reader
                            should land. */}
                        <p className="mono mt-1 text-[11px] leading-relaxed text-[rgb(var(--faint))]">
                          {cell.refs.map((ref, index) => {
                            const [incidentId] = ref.split("#");
                            return (
                              <span key={ref}>
                                {index > 0 && ", "}
                                <Link
                                  href={`/incidents/${encodeURIComponent(incidentId)}${hrefFor(ref, incidentId)}`}
                                  className="focusable whitespace-nowrap rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                                >
                                  {ref}
                                </Link>
                              </span>
                            );
                          })}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p data-not-observed className="mt-2 text-xs text-[rgb(var(--faint))]">
                    not observed
                  </p>
                )}
              </li>
            ))}
          </ol>
        </div>
      </Panel>

      <Panel title="What an empty column means" aside="and what it does not">
        <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
          <em>Observed</em> means {matrix.meaning.observed}. <em>Not observed</em> means{" "}
          {matrix.meaning.not_observed}. The library is{" "}
          <span className="tnum">{matrix.incident_count}</span> written scenarios carrying{" "}
          <span className="tnum">{matrix.step_count}</span> technique-mapped steps; the{" "}
          <span className="tnum">{matrix.unobserved_tactics.length}</span> tactics with nothing
          under them — {matrix.unobserved_tactics.join(", ")} — are tactics no scenario was
          written to show, and this page will not say anything else about them.
        </p>
        <p className="mt-3 text-xs text-[rgb(var(--faint))]">
          A technique identifier is a citation, not a finding: it says what a step resembles,
          not that the step is proven. The steps are on the{" "}
          <Link href="/incidents" className="focusable rounded underline decoration-dotted">
            incidents
          </Link>{" "}
          themselves.
        </p>
      </Panel>
    </Page>
  );
}
