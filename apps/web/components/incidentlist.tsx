import Link from "next/link";

import { Ago, Badge, statusForSeverity } from "@/components/ui";
import type { Incident } from "@/lib/api";
import { KINDS, headline, kindOf } from "@/lib/incidentkinds";

/**
 * Real incidents as rows, not cards.
 *
 * A scenario card is a screen tall, which worked for five; the live list holds dozens and the
 * record thousands. Each row carries what a reader triages on — severity, what kind of event, the
 * claim, when, and who published it — and opens the full incident, where the evidence is.
 * `stacked` keeps every row in one column, for a panel too narrow for the three-column row.
 */
export function IncidentRows({ incidents, stacked = false }: { incidents: Incident[]; stacked?: boolean }) {
  const wide = (classes: string) => (stacked ? "" : classes);
  return (
    <ul className="divide-y divide-[rgb(var(--edge))] overflow-hidden rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]">
      {incidents.map((incident) => {
        const kind = kindOf(incident.id);
        const statement = incident.hypotheses[0]?.statement ?? incident.id;
        return (
          <li key={incident.id}>
            <Link
              href={`/incidents/${encodeURIComponent(incident.id)}`}
              className={`focusable flex flex-col gap-1.5 px-4 py-3 hover:bg-[rgb(var(--raised))] ${wide("sm:flex-row sm:items-start sm:gap-4")}`}
            >
              <span className={`flex shrink-0 items-center gap-2 ${wide("sm:w-56")}`}>
                <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
                {kind && <span className="text-xs text-[rgb(var(--muted))]">{KINDS[kind].label}</span>}
              </span>
              <span className="min-w-0 flex-1 text-sm leading-snug text-[rgb(var(--ink))]">
                {headline(statement)}
              </span>
              <span className={`flex shrink-0 gap-3 text-xs text-[rgb(var(--faint))] ${wide("sm:w-44 sm:flex-col sm:items-end sm:gap-0.5")}`}>
                <Ago at={incident.opened_at} />
                {kind && <span>{KINDS[kind].source}</span>}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
