/**
 * What this incident reached, as a list and as a shape.
 *
 * The list is the content. It is what a screen reader gets, what remains below
 * `lg`, and what carries the entities the walk could not draw — R63 asks for
 * the diagram to collapse to the list on narrow viewports rather than overflow,
 * so the list has to be complete on its own rather than be a caption for a
 * picture.
 *
 * The origin is the incident's first affected entity: where the thing started,
 * which is the only reading of "blast radius" that is a property of the
 * incident rather than of whichever node was clicked.
 */

import Link from "next/link";

import { BlastGraph } from "@/components/blastgraph";
import { Empty, Panel } from "@/components/ui";
import { getBlastRadius, type Incident } from "@/lib/api";

export async function BlastPanel({ incident }: { incident: Incident }) {
  const origin = incident.affected_entities[0];
  if (!origin) return null;

  const key = `${origin.kind}:${origin.id}`;
  const radius = await getBlastRadius(key);
  // Silent rather than an error panel. Blast radius illustrates a count that is
  // already on the page; a broken box explaining that a picture is missing is
  // worse than the picture being missing.
  if (!radius || radius.entity_count === 0) return null;

  const drawn = new Set((radius.reached ?? []).map((node) => node.key));

  return (
    <Panel
      title="What this reached"
      aside={`from ${origin.name} · ${radius.entity_count} ${
        radius.entity_count === 1 ? "entity" : "entities"
      }`}
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <ol className="divide-y divide-[rgb(var(--edge))]">
            {radius.affected.map((entityKey) => {
              const node = (radius.reached ?? []).find((row) => row.key === entityKey);
              return (
                <li
                  key={entityKey}
                  className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 first:pt-0 last:pb-0"
                >
                  <Link
                    href={`/entity/${entityKey}`}
                    className="focusable mono min-w-0 break-all rounded text-sm text-[rgb(var(--astra))] underline decoration-dotted underline-offset-2"
                  >
                    {entityKey}
                  </Link>
                  {node ? (
                    <span className="text-[11px] text-[rgb(var(--faint))]">
                      {node.depth === 1 ? "directly" : `${node.depth} hops away`}
                    </span>
                  ) : (
                    // Named, not omitted. A node in the reach that no cited edge
                    // explains is a real gap in the evidence, and dropping it
                    // would make this list disagree with the count above it.
                    <span className="text-[11px] text-[rgb(var(--warn))]">
                      <span aria-hidden="true">◆</span> no cited path
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
          {radius.estimated_users > 0 && (
            <p className="mt-3 text-xs text-[rgb(var(--muted))]">
              Roughly {radius.estimated_users.toLocaleString()} users sit behind
              those entities.
            </p>
          )}
          {drawn.size === 0 && (
            <p className="mt-3 text-xs text-[rgb(var(--warn))]">
              No path here is established by cited evidence, so nothing is drawn.
            </p>
          )}
        </div>

        <BlastGraph radius={radius} />
      </div>
    </Panel>
  );
}
