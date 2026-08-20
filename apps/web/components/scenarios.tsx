import Link from "next/link";

import { Badge, statusForSeverity } from "@/components/ui";
import type { Incident } from "@/lib/api";

/**
 * Switch between the scripted scenarios.
 *
 * Three incidents existed and nothing invited anyone to look at more than the
 * first, which is the difference between a screenshot and something a person
 * actually clicks through. Each card says what its scenario is *about* rather
 * than only naming it, because the interesting part of these is not the attack
 * but the reading that looked right and was wrong.
 *
 * Everything shown is derived from the incident the API returned — the
 * diagnosis, the alternative it ruled out, the techniques. Nothing about these
 * scenarios is described twice, so nothing can drift out of step with them.
 *
 * **These are links, not a "simulate" button.** Running a scenario on demand
 * means writing state, and this API keeps state in the process: on Lambda a
 * write lands in one container and the next read may reach another, so the
 * button would work most of the time and fail unpredictably. Every scenario is
 * seeded into every container at startup instead, so switching cannot fail.
 * Triggering one for real is worth doing once state is durable (R18).
 */

/** The claim, without the sentence that elaborates it. */
function headline(incident: Incident): string {
  const statement = incident.hypotheses[0]?.statement ?? incident.id;
  const clause = statement.split(/[:.]\s/)[0];
  return clause.length > 96 ? `${clause.slice(0, 95)}…` : clause;
}

/** The reading that was considered and ruled out — the point of the scenario. */
function alternative(incident: Incident): string | null {
  const other = incident.hypotheses.find((h) => h.contradicted_by.length > 0);
  return other ? other.statement : null;
}

export function Scenarios({
  incidents,
  currentId,
}: {
  incidents: Incident[];
  currentId?: string;
}) {
  if (incidents.length < 2) return null;

  return (
    <section aria-label="Scenarios">
      <h2 className="label">Scenarios · {incidents.length}</h2>
      <p className="mt-2 max-w-3xl text-xs text-[rgb(var(--muted))]">
        Each one carries a reading that is genuinely reasonable and turns out to be wrong.
        The evidence that rules it out is cited and can be followed.
      </p>

      <ul className="mt-4 grid gap-3 lg:grid-cols-3">
        {incidents.map((incident) => {
          const current = incident.id === currentId;
          const ruled = alternative(incident);
          const tactics = [
            ...new Set(
              incident.causal_chain
                .map((link) => link.attack_technique?.tactic)
                .filter((t): t is string => Boolean(t)),
            ),
          ];

          return (
            <li key={incident.id}>
              <Link
                href={`/incidents/${encodeURIComponent(incident.id)}`}
                aria-current={current ? "page" : undefined}
                className={`focusable panel block h-full p-4 transition-colors hover:bg-[rgb(var(--raised))] ${
                  current
                    ? "border-[rgb(var(--astra))]/50 bg-[rgb(var(--raised))]"
                    : ""
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge status={statusForSeverity(incident.severity)}>
                    {incident.severity}
                  </Badge>
                  {current && (
                    <span className="text-[10px] uppercase tracking-[0.14em] text-[rgb(var(--astra))]">
                      viewing
                    </span>
                  )}
                  <span className="mono ml-auto text-[11px] text-[rgb(var(--muted))]">
                    {incident.id}
                  </span>
                </div>

                <p className="mt-3 text-sm text-[rgb(var(--ink))]">{headline(incident)}</p>

                {ruled && (
                  <p className="mt-2 text-xs text-[rgb(var(--muted))]">
                    <span className="text-[rgb(var(--faint))]">ruled out: </span>
                    {ruled}
                  </p>
                )}

                {tactics.length > 0 && (
                  <p className="mono mt-3 text-[10px] uppercase tracking-wide text-[rgb(var(--faint))]">
                    {tactics.join(" · ")}
                  </p>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
