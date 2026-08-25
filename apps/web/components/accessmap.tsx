/**
 * The access map, wherever it is drawn.
 *
 * Extracted from `/infrastructure` so the incident page can show the same thing
 * for its own entities (R51). A second implementation would have been quicker
 * and would have drifted — and the half that drifts is always the one drawn
 * less often, which here is the one an operator looks at during an incident.
 *
 * The map is the same in both places on purpose. Someone who has learned to
 * read it on the whole estate should not have to learn it again on one
 * incident: same colours, same arrow direction, same left-to-right meaning.
 */

import type { GraphEdge, GraphNode } from "@/lib/api";
import { layout, NODE_HEIGHT, NODE_WIDTH } from "@/lib/layout";

export const STATUS = {
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
    className: "text-[rgb(var(--faint))]", stroke: "rgb(var(--muted))",
  },
} as const;

export function statusOf(node: GraphNode) {
  return STATUS[node.severity ?? "unknown"];
}

/** The whole node as one sentence, for anyone reading the map without seeing it.
 *  Built as a single string rather than as sibling text nodes: the latter is
 *  what React splits with comment markers, and it is what made this element
 *  disagree with itself between server and client. */
export function describe(node: GraphNode, status: string): string {
  const parts = [node.key];
  if (node.namespace) parts.push(node.namespace);
  parts.push(status);
  if (node.estimated_users) parts.push(`~${node.estimated_users} users`);
  return parts.join(" · ");
}

export function truncate(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

export function tally(nodes: GraphNode[]) {
  const counts = { critical: 0, warning: 0, info: 0, unknown: 0 };
  for (const node of nodes) counts[node.severity ?? "unknown"] += 1;
  return counts;
}

export function AccessMap({
  nodes,
  edges,
  label,
  idPrefix = "map",
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  label: string;
  /** Marker ids must be unique per document. Two maps on one page sharing
   *  `#arrow` means the second one's arrowheads resolve to the first one's
   *  definition — which works until the first is conditionally not rendered,
   *  and then the arrows silently vanish from the second. */
  idPrefix?: string;
}) {
  const placed = layout(nodes, edges);
  const arrow = `${idPrefix}-arrow`;

  return (
    // `max-w-full` and `min-w-0` alongside the scroller, not instead of it.
    // `overflow-x-auto` only scrolls a box that is *narrower than its content*,
    // and this box had no width limit — so it grew to the SVG's intrinsic 954px
    // and pushed the whole document sideways at 375px, with the scroller
    // present and inert the entire time.
    <div className="min-w-0 max-w-full overflow-x-auto">
      <svg
        width={placed.width}
        height={placed.height}
        viewBox={`0 0 ${placed.width} ${placed.height}`}
        role="img"
        aria-label={label}
        className="min-w-full"
      >
        <defs>
          <marker
            id={arrow}
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
            markerEnd={`url(#${arrow})`}
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
                  mismatch that discarded and re-rendered this whole subtree on
                  every load, silently, because the map still looked right. */}
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
  );
}
