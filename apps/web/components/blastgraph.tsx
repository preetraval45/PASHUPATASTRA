/**
 * Blast radius as a shape rather than a count.
 *
 * "Three entities" and "this workstation reached a file share, an application
 * host, and a scheduled task running on it" are the same fact, and only one of
 * them tells an operator whether to care. The ring per hop is the part a number
 * cannot carry: what was touched directly, and what was touched through
 * something else.
 *
 * **No edge without a citation.** Enforced in the walk rather than here — the
 * API refuses to cross an edge carrying no evidence, so a line on this diagram
 * cannot exist without event ids behind it. Filtering at render time would have
 * left the node reachable and the reason invisible, which is how a picture ends
 * up asserting a relationship nobody can check.
 *
 * **The list is the content; this is the illustration.** The list is rendered
 * by the caller either way, is what a screen reader gets, and is what remains
 * on a narrow viewport. This is `aria-hidden` and hidden below `lg` — a radial
 * diagram at 375px is an overflow, and R63 asks for it to collapse to the list
 * rather than scroll sideways.
 */

import type { BlastRadius } from "@/lib/api";

const SIZE = 320;
const CENTRE = SIZE / 2;
const RING = 82;
const NODE_R = 5.5;

const SEVERITY: Record<string, string> = {
  critical: "rgb(var(--crit))",
  warning: "rgb(var(--warn))",
  info: "rgb(var(--ok))",
};

function colourOf(severity: string | null | undefined): string {
  return SEVERITY[severity ?? ""] ?? "rgb(var(--muted))";
}

/** Position for one node: ring by hop distance, angle by index within the ring.
 *
 *  Laid out deterministically from the data rather than by a force simulation.
 *  A simulation would settle differently on every render, so two people looking
 *  at the same incident would be describing different pictures — and it would
 *  need to run before the page could draw, which Phase 5 forbids. */
function place(depth: number, index: number, count: number) {
  const radius = RING * depth;
  // Start at the top and go clockwise. `count` in the denominator spreads the
  // ring evenly however many landed on it.
  const angle = (index / Math.max(count, 1)) * Math.PI * 2 - Math.PI / 2;
  return {
    x: CENTRE + radius * Math.cos(angle),
    y: CENTRE + radius * Math.sin(angle),
  };
}

export function BlastGraph({ radius }: { radius: BlastRadius }) {
  const reached = radius.reached ?? [];
  if (reached.length === 0) return null;

  const byDepth = new Map<number, typeof reached>();
  for (const node of reached) {
    byDepth.set(node.depth, [...(byDepth.get(node.depth) ?? []), node]);
  }

  const at = new Map<string, { x: number; y: number }>();
  at.set(radius.origin, { x: CENTRE, y: CENTRE });
  for (const [depth, nodes] of byDepth) {
    nodes.forEach((node, index) => {
      at.set(node.key, place(depth, index, nodes.length));
    });
  }

  const deepest = Math.max(...reached.map((node) => node.depth));

  return (
    <div className="hidden lg:block" aria-hidden="true">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="h-auto w-full max-w-[320px]"
        role="presentation"
      >
        {/* One faint circle per hop, so "directly" and "through something else"
            are visible without reading a single label. */}
        {Array.from({ length: deepest }, (_, index) => (
          <circle
            key={index}
            cx={CENTRE}
            cy={CENTRE}
            r={RING * (index + 1)}
            fill="none"
            stroke="rgb(var(--edge))"
            strokeDasharray="2 4"
          />
        ))}

        {(radius.edges ?? []).map((edge) => {
          const from = at.get(edge.source);
          const to = at.get(edge.target);
          if (!from || !to) return null;
          return (
            <line
              key={`${edge.source}->${edge.target}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="rgb(var(--edge-strong))"
              strokeWidth={1}
              // The citation, carried on the element rather than in a `<title>`.
              //
              // React 19 treats `<title>` as document metadata and hoists it,
              // which put a hydration mismatch (#418) on every incident page.
              // An SVG title is a tooltip; a data attribute is the same fact
              // without asking the renderer to guess which `<title>` this is.
              data-kind={edge.kind}
              data-evidence={edge.evidence.join(", ")}
            />
          );
        })}

        <circle
          cx={CENTRE}
          cy={CENTRE}
          r={NODE_R + 2}
          fill="rgb(var(--ground))"
          stroke="rgb(var(--astra))"
          strokeWidth={1.5}
        />

        {reached.map((node) => {
          const point = at.get(node.key);
          if (!point) return null;
          return (
            <g key={node.key}>
              <circle
                cx={point.x}
                cy={point.y}
                r={NODE_R}
                fill="rgb(var(--ground))"
                stroke={colourOf(node.severity)}
                strokeWidth={1.5}
              />
              <text
                x={point.x}
                y={point.y - 10}
                textAnchor="middle"
                className="fill-[rgb(var(--muted))] text-[9px]"
              >
                {node.name.length > 18 ? `${node.name.slice(0, 17)}…` : node.name}
              </text>
            </g>
          );
        })}
      </svg>

      <p className="mt-2 text-[11px] leading-relaxed text-[rgb(var(--faint))]">
        {reached.length} reached through {radius.edges?.length ?? 0} cited{" "}
        {radius.edges?.length === 1 ? "path" : "paths"}, {deepest}{" "}
        {deepest === 1 ? "hop" : "hops"} deep.
        {radius.uncited && radius.uncited.length > 0 && (
          <>
            {" "}
            {radius.uncited.length} more{" "}
            {radius.uncited.length === 1 ? "entity is" : "entities are"} in the
            reach with no cited path, listed but not drawn.
          </>
        )}
      </p>
    </div>
  );
}
