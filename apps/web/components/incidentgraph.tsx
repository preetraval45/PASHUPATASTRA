/**
 * The incident's own access paths, beside the incident.
 *
 * The map standing alone on `/infrastructure` is a screensaver: all green,
 * nobody's problem, nothing to decide. Rendered here — *these* entities, what
 * they can reach, which of them is already compromised — it is the screen that
 * shows the system has a model of the estate rather than a language model
 * narrating log lines.
 *
 * Only what this incident's evidence names. A path from one of these entities
 * out to something the incident never mentions is real and is not drawn: doing
 * so would say the incident reached further than its evidence establishes,
 * which is the rule R50 applied to inventing edges, applied to borrowing them.
 */

import Link from "next/link";

import { AccessMap, statusOf } from "@/components/accessmap";
import { Empty, Ident, Panel } from "@/components/ui";
import { getIncidentGraph, type Incident } from "@/lib/api";

export async function IncidentGraph({ incident }: { incident: Incident }) {
  const graph = await getIncidentGraph(incident.id);
  if (graph === null) return null;

  const { nodes, edges, beyond } = graph;
  const connected = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const isolated = nodes.filter((node) => !connected.has(node.key));

  return (
    <Panel
      title="What this reached"
      aside={
        <Link
          href="/infrastructure"
          className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
        >
          the whole map →
        </Link>
      }
    >
      {edges.length === 0 ? (
        <Empty art="ledger" title="No access paths recorded for this incident.">
          Seeing an entity establishes that it is there. Only an observed access
          — a session, a connection, a token — establishes that it could reach
          something else.
        </Empty>
      ) : (
        <>
          <p className="mb-3 text-sm text-[rgb(var(--muted))]">
            Left to right is the direction an intrusion spreads: each arrow
            points at what the thing on the left depends on staying honest.
          </p>

          {/* Its own marker prefix. Two maps on one page sharing `#arrow` means
              the second one's arrowheads resolve to the first one's definition,
              which works until the first is not rendered. */}
          <AccessMap
            nodes={nodes}
            edges={edges}
            idPrefix={`inc-${incident.id}`}
            label={`Access paths recorded for ${incident.id}`}
          />

          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-[rgb(var(--edge))] pt-4 text-xs">
            <div className="flex gap-2">
              <dt className="text-[rgb(var(--faint))]">entities</dt>
              <dd className="mono">{nodes.length}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-[rgb(var(--faint))]">access paths</dt>
              <dd className="mono">{edges.length}</dd>
            </div>
            <div className="flex gap-2">
              {/* Counted, not drawn. Zero here is a real finding — nothing
                  observed leads out of this incident — and it reads very
                  differently from a number, which is why it is stated rather
                  than left as an absence. */}
              <dt className="text-[rgb(var(--faint))]">reachable beyond it</dt>
              <dd className="mono">{beyond.length}</dd>
            </div>
          </dl>

          {beyond.length > 0 && (
            <p className="mt-2 text-xs text-[rgb(var(--muted))]">
              These entities can also reach{" "}
              {beyond.slice(0, 4).map((key, index) => (
                <span key={key}>
                  {index > 0 && ", "}
                  <Link
                    href={`/entity/${encodeURIComponent(key)}`}
                    className="focusable rounded underline decoration-dotted underline-offset-2"
                  >
                    {key}
                  </Link>
                </span>
              ))}
              {beyond.length > 4 && ` and ${beyond.length - 4} more`} — outside
              what this incident&rsquo;s evidence covers.
            </p>
          )}
        </>
      )}

      {isolated.length > 0 && (
        <p className="mt-4 border-t border-[rgb(var(--edge))] pt-3 text-xs text-[rgb(var(--muted))]">
          Named by the incident with no access observed either way:{" "}
          {isolated.map((node, index) => (
            <span key={node.key}>
              {index > 0 && ", "}
              <span className={statusOf(node).className} aria-hidden="true">
                {statusOf(node).glyph}
              </span>{" "}
              <Ident>{node.key}</Ident>
            </span>
          ))}
          .
        </p>
      )}
    </Panel>
  );
}
