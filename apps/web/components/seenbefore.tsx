import Link from "next/link";

import { Ago, Badge, Panel, statusForSeverity } from "@/components/ui";
import type { SimilarIncident } from "@/lib/api";
import { KINDS, headline, kindOf } from "@/lib/incidentkinds";

/**
 * "Have we seen this before?" — past incidents from the record that resemble this one.
 *
 * Ranked by the API from the words two incidents share, each weighted by how rare it is in the
 * record, so a ransomware group's name or a product counts and a stock phrase does not. The words
 * are shown beside each match: a resemblance a reader cannot check is a claim without evidence.
 */
export function SeenBefore({ items }: { items: SimilarIncident[] }) {
  if (items.length === 0) return null;
  return (
    <Panel title="Seen before" aside="from the record, by the rare words they share">
      <ul className="divide-y divide-[rgb(var(--edge))]">
        {items.map(({ incident, shared }) => {
          const kind = kindOf(incident.id);
          return (
            <li key={incident.id} className="py-3 first:pt-0 last:pb-0">
              <Link href={`/incidents/${encodeURIComponent(incident.id)}`} className="focusable block rounded">
                <span className="flex flex-wrap items-center gap-2">
                  <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
                  {kind && <span className="text-xs text-[rgb(var(--muted))]">{KINDS[kind].label}</span>}
                  <span className="ml-auto text-xs text-[rgb(var(--faint))]">
                    <Ago at={incident.opened_at} />
                  </span>
                </span>
                <span className="mt-1 block text-sm text-[rgb(var(--ink))]">
                  {headline(incident.hypotheses[0]?.statement ?? incident.id)}
                </span>
                <span className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-[rgb(var(--muted))]">
                  shares
                  {shared.map((word) => (
                    <code key={word} className="mono rounded border border-[rgb(var(--edge))] px-1">
                      {word}
                    </code>
                  ))}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
