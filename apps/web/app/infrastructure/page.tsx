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
const STATUS = {
  critical: { glyph: "▲", label: "critical", className: "text-rose-400", stroke: "#fb7185" },
  warning: { glyph: "◆", label: "degraded", className: "text-amber-400", stroke: "#fbbf24" },
  info: { glyph: "●", label: "healthy", className: "text-emerald-400", stroke: "#34d399" },
  unknown: { glyph: "○", label: "no data", className: "text-[rgb(var(--muted))]", stroke: "#4b5563" },
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
        <Empty title="No topology yet.">
          Run a Drishti poll to populate it from Prometheus, Kubernetes, or Docker.
        </Empty>
      </Page>
    );
  }

  // Cluster infrastructure — CoreDNS, kube-proxy, etcd — outnumbers the
  // workload on any real cluster and would bury it. Hidden by default, but the
  // count is always stated: a map that silently drops entities reads as
  // "this is everything", which is exactly the wrong impression during an
  // incident.
  const hidden = snapshot.nodes.filter(isInfrastructure);
  const visible = showAll ? snapshot.nodes : snapshot.nodes.filter((n) => !isInfrastructure(n));
  const visibleKeys = new Set(visible.map((n) => n.key));
  const edges = snapshot.edges.filter(
    (e) => visibleKeys.has(e.source) && visibleKeys.has(e.target),
  );

  // Rank 0 means "nothing depends on this" — a caller, an entry point. A node
  // with no edges at all means something different: we have not observed its
  // dependencies yet. Drawing them in the same column would state the first
  // when only the second is true, which is a claim the graph cannot support.
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
      description="What depends on what. Callers on the left, their dependencies to the right — so a failure propagates right-to-left across this map."
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
            {visible.length} entities · {edges.length} dependencies
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
          No dependencies observed yet. Traces and Kubernetes ownership create edges;
          metrics alone establish only that an entity exists.
        </div>
      ) : (
      <div className="panel overflow-x-auto p-2">
        <svg
          width={placed.width}
          height={placed.height}
          viewBox={`0 0 ${placed.width} ${placed.height}`}
          role="img"
          aria-label="Service dependency map"
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
        <Panel title={`No observed dependencies yet · ${isolated.length}`}>
          <p className="text-xs text-[rgb(var(--muted))]">
            These entities are known to exist but nothing has yet revealed what they depend
            on. Metrics prove existence; only traces and platform ownership prove
            dependency — so this list shrinks as coverage improves, and it is worth
            watching for anything that ought to be connected.
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
          Dependency table
          <span className="ml-2 normal-case tracking-normal text-[rgb(var(--faint))]">
            — the same data as the map, for screen readers, search, and copy-paste
          </span>
        </summary>
        <div className="overflow-x-auto border-t border-[rgb(var(--edge))]">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <caption className="sr-only">
              Every mapped entity with its status and what it depends on
            </caption>
            <thead>
              <tr className="border-b border-[rgb(var(--edge))] text-[rgb(var(--muted))]">
                <th scope="col" className="px-5 py-2 font-medium">Entity</th>
                <th scope="col" className="px-5 py-2 font-medium">Kind</th>
                <th scope="col" className="px-5 py-2 font-medium">Status</th>
                <th scope="col" className="px-5 py-2 font-medium">Depends on</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgb(var(--edge))]">
              {placed.nodes.map((node) => {
                const status = statusOf(node);
                const dependencies = edges
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
                      {dependencies.join(", ") || "—"}
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
          <li>Solid lines are observed dependencies — a trace recorded the call.</li>
          <li>Dashed lines are ownership, declared by the platform.</li>
          <li>
            Position is deterministic: a node stays put until its dependencies change, so this
            map is comparable with the one you saw ten minutes ago.
          </li>
          <li>Severity is the worst reading in the last 15 minutes, not the most recent.</li>
          <li>
            Cluster infrastructure is hidden by default and counted above — never dropped
            silently.
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
