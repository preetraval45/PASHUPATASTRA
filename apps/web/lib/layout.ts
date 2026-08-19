/**
 * Deterministic layered layout for the reachability map.
 *
 * Deterministic matters more than pretty here. A force-directed graph settles
 * somewhere different on every render, so an operator comparing the map to what
 * they saw ten minutes ago has to re-find every node. During an incident that is
 * a real cost. Rank-based layout means an entity sits in the same place until
 * what it can reach actually changes.
 *
 * Rank follows reach: an entry point on the left, what it can touch to the
 * right, so an intrusion reads left-to-right the way it would actually spread.
 */

import type { GraphEdge, GraphNode } from "./api";

export interface PlacedNode extends GraphNode {
  x: number;
  y: number;
  rank: number;
}

export interface PlacedEdge extends GraphEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Layout {
  nodes: PlacedNode[];
  edges: PlacedEdge[];
  width: number;
  height: number;
}

const COLUMN_WIDTH = 240;
const ROW_HEIGHT = 62;
const MARGIN_X = 24;
const MARGIN_Y = 28;

export function layout(nodes: GraphNode[], edges: GraphEdge[]): Layout {
  const byKey = new Map(nodes.map((n) => [n.key, n]));
  const present = edges.filter((e) => byKey.has(e.source) && byKey.has(e.target));

  const rank = computeRanks(nodes, present);

  // Group by rank, then order within a column by severity first so the things
  // demanding attention sit together at the top rather than scattered.
  const columns = new Map<number, GraphNode[]>();
  for (const node of nodes) {
    const r = rank.get(node.key) ?? 0;
    if (!columns.has(r)) columns.set(r, []);
    columns.get(r)!.push(node);
  }

  const placed: PlacedNode[] = [];
  for (const [r, column] of [...columns].sort((a, b) => a[0] - b[0])) {
    column.sort(
      (a, b) =>
        severityWeight(b.severity) - severityWeight(a.severity) ||
        a.name.localeCompare(b.name),
    );
    column.forEach((node, index) => {
      placed.push({
        ...node,
        rank: r,
        x: MARGIN_X + r * COLUMN_WIDTH,
        y: MARGIN_Y + index * ROW_HEIGHT,
      });
    });
  }

  const position = new Map(placed.map((n) => [n.key, n]));
  const placedEdges: PlacedEdge[] = present.map((edge) => {
    const from = position.get(edge.source)!;
    const to = position.get(edge.target)!;
    return {
      ...edge,
      x1: from.x + NODE_WIDTH,
      y1: from.y + NODE_HEIGHT / 2,
      x2: to.x,
      y2: to.y + NODE_HEIGHT / 2,
    };
  });

  const maxRank = Math.max(0, ...placed.map((n) => n.rank));
  const maxRow = Math.max(1, ...[...columns.values()].map((c) => c.length));

  return {
    nodes: placed,
    edges: placedEdges,
    width: MARGIN_X * 2 + maxRank * COLUMN_WIDTH + NODE_WIDTH,
    height: MARGIN_Y * 2 + maxRow * ROW_HEIGHT,
  };
}

/**
 * Longest-path rank. Longest rather than shortest so a node always sits to the
 * right of everything that depends on it — with shortest paths an edge could
 * point backwards, which reads as traffic flowing the wrong way.
 */
function computeRanks(nodes: GraphNode[], edges: GraphEdge[]): Map<string, number> {
  const outgoing = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  for (const node of nodes) {
    outgoing.set(node.key, []);
    indegree.set(node.key, 0);
  }
  for (const edge of edges) {
    outgoing.get(edge.source)!.push(edge.target);
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
  }

  const rank = new Map(nodes.map((n) => [n.key, 0]));
  const queue = nodes.filter((n) => (indegree.get(n.key) ?? 0) === 0).map((n) => n.key);
  const seen = new Set(queue);

  while (queue.length) {
    const key = queue.shift()!;
    for (const next of outgoing.get(key) ?? []) {
      rank.set(next, Math.max(rank.get(next) ?? 0, (rank.get(key) ?? 0) + 1));
      const remaining = (indegree.get(next) ?? 1) - 1;
      indegree.set(next, remaining);
      if (remaining === 0 && !seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }

  // Anything still unseen sits in a cycle. Kahn's algorithm cannot rank it, so
  // it keeps rank 0 and renders at the left rather than vanishing — a cyclic
  // dependency is worth seeing, not worth hiding.
  return rank;
}

export const NODE_WIDTH = 186;
export const NODE_HEIGHT = 40;

export function severityWeight(severity: string | null): number {
  return { critical: 3, warning: 2, info: 1 }[severity ?? ""] ?? 0;
}
