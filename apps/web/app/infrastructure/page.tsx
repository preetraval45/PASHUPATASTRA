import Link from "next/link";

import { Empty, Offline, Page, Panel } from "@/components/ui";
import { getTopology, isInfrastructure, type GraphNode } from "@/lib/api";
import { layout, NODE_HEIGHT, NODE_WIDTH, severityWeight } from "@/lib/layout";

export const dynamic = "force-dynamic";

/**
 * Status is never carried by colour alone: every node shows a glyph and, when
 * degraded, the state in words. An operator with a colour-vision deficiency,
 * or a screenshot pasted into a monochrome ticket, must read the same thing.
 */
// Tokens, not literals. These were `text-rose-400` and `#fb7185` — the dark
// palette, hardcoded — so the map kept dark-theme status colours on a white
// page and the glyphs measured 1.6:1 to 2.7:1 in light mode. The classes are
// written out rather than composed from a token name because Tailwind reads
// source text, and a class assembled at runtime is a class it never generates.
const STATUS = {
  critical: {
    glyph: "▲", label: "critical",
    className: "text-[rgb(var(--crit))]", stroke: "rgb(var(--crit))",
  },
  warning: {
    glyph: "◆", label: "degraded",
    className: "text-[rgb(var(--warn))]", stroke: "rgb(var(--warn))",
  },
  info: {
    glyph: "●", label: "healthy",
    className: "text-[rgb(var(--ok))]", stroke: "rgb(var(--ok))",
  },
  unknown: {
    glyph: "○", label: "no data",
    className: "text-[rgb(var(--muted))]", stroke: "rgb(var(--edge-strong))",
  },
} as const;

function statusOf(node: GraphNode) {
  return STATUS[node.severity ?? "unknown"];
}

/** The whole node as one sentence, for anyone reading the map without seeing it.
 *  Built as a single string rather than as sibling text nodes: the latter is
 *  what React splits with comment markers, and it is what made this element
 *  disagree with itself between server and client. */
function describe(node: GraphNode, status: string): string {
  const parts = [node.key];
  if (node.namespace) parts.push(node.namespace);
  parts.push(status);
  if (node.estimated_users) parts.push(`~${node.estimated_users} users`);
  return parts.join(" · ");
}

export default async function InfrastructurePage({
  searchParams,
}: {
  searchParams: Promise<{ scope?: string }>;
}) {
  const { scope } = await searchParams;
  const showAll = scope === "all";
  const snapshot = await getTopology();

  if (!snapshot) return <Offline />;

  if (snapshot.nodes.length === 0) {
    return (
      <Page title="Infrastructure">
        <Empty title="Nothing observed yet.">
          Nothing has been observed yet. Drishti populates this as collectors report
          hosts, accounts, processes and the connections between them.
        </Empty>
      </Page>
    );
  }

  // Platform-owned entities outnumber the ones anyone is watching for and
  // would bury them. Hidden by default, but the
  // count is always stated: a map that silently drops entities reads as
  // "this is everything", which is exactly the wrong impression during an
  // incident.
  const hidden = snapshot.nodes.filter(isInfrastructure);
  const visible = showAll ? snapshot.nodes : snapshot.nodes.filter((n) => !isInfrastructure(n));
  const visibleKeys = new Set(visible.map((n) => n.key));
  const edges = snapshot.edges.filter(
    (e) => visibleKeys.has(e.source) && visibleKeys.has(e.target),
  );

  // Rank 0 means "nothing reaches this" — an entry point, which is where an
  // intrusion starts. A node with no edges at all means something different:
  // we have not observed what it can reach yet. Drawing them in the same
  // column would state the first when only the second is true, which is a
  // claim the graph cannot support.
  const connectedKeys = new Set(edges.flatMap((e) => [e.source, e.target]));
  const connected = visible.filter((n) => connectedKeys.has(n.key));
  const isolated = visible
    .filter((n) => !connectedKeys.has(n.key))
    .sort(
      (a, b) => severityWeight(b.severity) - severityWeight(a.severity) ||
        a.name.localeCompare(b.name),
    );

  const placed = layout(connected, edges);
  const counts = tally(visible);

  return (
    <Page
      title="Infrastructure"
      description="What can reach what. An account or host on the left, what it can touch to the right — so an intrusion spreads left-to-right across this map."
    >

      <section className="flex flex-wrap gap-x-6 gap-y-2 text-xs">
        {(["critical", "warning", "info", "unknown"] as const).map((key) => (
          <span key={key} className="flex items-center gap-2">
            <span className={STATUS[key].className}>{STATUS[key].glyph}</span>
            <span className="text-[rgb(var(--muted))]">
              {STATUS[key].label} · {counts[key]}
            </span>
          </span>
        ))}
        <span className="ml-auto flex items-center gap-3 text-[rgb(var(--muted))]">
          <span>
            {visible.length} entities · {edges.length} access paths
          </span>
          {hidden.length > 0 && (
            <Link
              href={showAll ? "/infrastructure" : "/infrastructure?scope=all"}
              className="rounded border border-[rgb(var(--edge))] px-2 py-0.5 hover:text-[rgb(var(--ink))]"
            >
              {showAll
                ? `hide ${hidden.length} infrastructure`
                : `${hidden.length} infrastructure hidden — show`}
            </Link>
          )}
        </span>
      </section>

      {connected.length === 0 ? (
        <div className="panel p-6 text-sm text-[rgb(var(--muted))]">
          No access observed yet. Connections, sessions and ownership create edges;
          seeing an entity establishes only that it is there.
        </div>
      ) : (
      <div className="panel overflow-x-auto p-2">
        <svg
          width={placed.width}
          height={placed.height}
          viewBox={`0 0 ${placed.width} ${placed.height}`}
          role="img"
          aria-label="Map of what can reach what"
          className="min-w-full"
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0 0 L8 4 L0 8 z" fill="rgb(var(--edge))" />
            </marker>
          </defs>

          {/* Connectors are recessive: the nodes carry the state, the lines only
              carry the relationship. */}
          {placed.edges.map((edge, index) => (
            <path
              key={`${edge.source}-${edge.target}-${index}`}
              d={`M ${edge.x1} ${edge.y1} C ${edge.x1 + 40} ${edge.y1}, ${edge.x2 - 40} ${edge.y2}, ${edge.x2} ${edge.y2}`}
              fill="none"
              stroke="rgb(var(--edge))"
              strokeWidth={edge.kind === "owned_by" ? 1 : 1.5}
              strokeDasharray={edge.kind === "owned_by" ? "3 3" : undefined}
              markerEnd="url(#arrow)"
            />
          ))}

          {placed.nodes.map((node) => {
            const status = statusOf(node);
            return (
              <g key={node.key} transform={`translate(${node.x}, ${node.y})`}>
                {/* The description is an `aria-label`, not an SVG <title>.
                    React 19 treats <title> as hoistable document metadata and
                    deduplicates it against the page title, so the server sent
                    `<title></title>` and the client filled it in — a hydration
                    mismatch that discarded and re-rendered this whole subtree
                    on every load, silently, because the map still looked right.
                    `aria-label` reaches a screen reader, which <title> here was
                    failing to do anyway. */}
                <a
                  href={`/entity/${node.key.split("/").map(encodeURIComponent).join("/")}`}
                  className="focusable"
                  aria-label={describe(node, status.label)}
                >
                <rect
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={6}
                  fill="rgb(var(--panel))"
                  stroke={status.stroke}
                  strokeWidth={node.severity === "critical" ? 1.75 : 1}
                />
                <text x={12} y={17} fontSize={11} fill={status.stroke}>
                  {status.glyph}
                </text>
                <text x={28} y={17} fontSize={12} fill="rgb(var(--ink))">
                  {truncate(node.name, 20)}
                </text>
                <text x={28} y={31} fontSize={10} fill="rgb(var(--muted))">
                  {node.kind}
                  {node.estimated_users > 0 && ` · ~${node.estimated_users} users`}
                </text>
                </a>
              </g>
            );
          })}
        </svg>
      </div>
      )}

      {isolated.length > 0 && (
        <Panel title={`Nothing observed reaching these yet · ${isolated.length}`}>
          <p className="text-xs text-[rgb(var(--muted))]">
            These entities are known to exist but nothing has yet shown what they can
            reach. Seeing an entity proves it is there; only an observed access proves it
            can touch something — so this list shrinks as coverage improves, and it is
            worth reading for anything that ought to be connected and is not.
          </p>
          <ul className="mt-4 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
            {isolated.map((node) => {
              const status = statusOf(node);
              return (
                <li key={node.key}>
                  <Link
                    href={`/entity/${node.key}`}
                    className="focusable flex items-center gap-2 rounded hover:text-[rgb(var(--ink))]"
                  >
                    <span className={status.className} aria-hidden="true">
                      {status.glyph}
                    </span>
                    <span className="mono truncate">{node.name}</span>
                    <span className="ml-auto shrink-0 text-[rgb(var(--muted))]">{node.kind}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}

      <details className="panel group">
        <summary className="focusable cursor-pointer list-none px-5 py-3 text-[11px] font-medium uppercase tracking-[0.14em] text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]">
          Access table
          <span className="ml-2 normal-case tracking-normal text-[rgb(var(--faint))]">
            — the same data as the map, for screen readers, search, and copy-paste
          </span>
        </summary>
        <div className="overflow-x-auto border-t border-[rgb(var(--edge))]">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <caption className="sr-only">
              Every mapped entity with its status and what it can reach
            </caption>
            <thead>
              <tr className="border-b border-[rgb(var(--edge))] text-[rgb(var(--muted))]">
                <th scope="col" className="px-5 py-2 font-medium">Entity</th>
                <th scope="col" className="px-5 py-2 font-medium">Kind</th>
                <th scope="col" className="px-5 py-2 font-medium">Status</th>
                <th scope="col" className="px-5 py-2 font-medium">Can reach</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgb(var(--edge))]">
              {placed.nodes.map((node) => {
                const status = statusOf(node);
                const reaches = edges
                  .filter((e) => e.source === node.key)
                  .map((e) => e.target);
                return (
                  <tr key={node.key}>
                    <th scope="row" className="px-5 py-2 text-left font-normal">
                      <Link href={`/entity/${node.key}`} className="focusable mono rounded">
                        {node.name}
                      </Link>
                    </th>
                    <td className="px-5 py-2 text-xs text-[rgb(var(--muted))]">{node.kind}</td>
                    <td className={`px-5 py-2 text-xs ${status.className}`}>
                      <span aria-hidden="true">{status.glyph} </span>
                      {status.label}
                    </td>
                    <td className="mono px-5 py-2 text-xs text-[rgb(var(--muted))]">
                      {reaches.join(", ") || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>

      <Panel title="Reading this map">
        <ul className="space-y-1 text-xs text-[rgb(var(--muted))]">
          <li>Solid lines are observed access — something recorded one reaching the other.</li>
          <li>Dashed lines are ownership — a host's processes, an account's sessions.</li>
          <li>
            Position is deterministic: a node stays put until what it can reach changes,
            so this map is comparable with the one you saw ten minutes ago.
          </li>
          <li>Severity is the worst reading in the last 15 minutes, not the most recent.</li>
          <li>
            Platform-owned entities are hidden by default and counted above — never
            dropped silently.
          </li>
        </ul>
      </Panel>
    </Page>
  );
}

function tally(nodes: GraphNode[]) {
  const counts = { critical: 0, warning: 0, info: 0, unknown: 0 };
  for (const node of nodes) counts[node.severity ?? "unknown"] += 1;
  return counts;
}

function truncate(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
