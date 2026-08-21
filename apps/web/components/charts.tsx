import { STATUS, type Status } from "@/components/ui";

/**
 * Small charts, drawn as inline SVG.
 *
 * No charting library: these are four shapes, and a dependency that ships a
 * layout engine to draw a bar would cost more than the page it decorates.
 *
 * **Every series here is passed in from data the API already returned.** None
 * of these components can generate a value, smooth a curve, or fill a gap —
 * a chart of invented numbers on a site whose whole argument is that it does
 * not invent things would undo the argument. Where there is nothing to plot
 * they render nothing and say so.
 */

/** A count per bucket, oldest first. */
export function Sparkline({
  values,
  status = "neutral",
  label,
  className = "",
}: {
  values: number[];
  status?: Status;
  label: string;
  className?: string;
}) {
  if (values.length < 2) return null;

  const width = 120;
  const height = 28;
  const peak = Math.max(...values, 1);
  const step = width / (values.length - 1);

  const points = values.map((v, i) => [i * step, height - (v / peak) * (height - 3)] as const);
  const line = points.map(([x, y], i) => `${i ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L ${width} ${height} L 0 ${height} Z`;
  const tint = STATUS[status].stroke;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`h-7 w-full ${className}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${label}: ${values.join(", ")}`}
    >
      <path d={area} fill={tint} fillOpacity="0.14" />
      <path d={line} fill="none" stroke={tint} strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="2" fill={tint} />
    </svg>
  );
}

/** Horizontal bars — a count per named band. */
export function Distribution({
  bands,
  total,
}: {
  bands: { label: string; count: number; status: Status }[];
  total?: number;
}) {
  const peak = Math.max(...bands.map((b) => b.count), 1);
  const sum = total ?? bands.reduce((n, b) => n + b.count, 0);

  return (
    <ul className="space-y-2.5">
      {bands.map((band) => (
        <li key={band.label} className="flex items-center gap-3 text-xs">
          <span className="w-24 shrink-0 text-[rgb(var(--muted))]">{band.label}</span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-[rgb(var(--raised))]">
            <span
              className="block h-full rounded-full"
              style={{
                width: `${(band.count / peak) * 100}%`,
                backgroundColor: STATUS[band.status].stroke,
              }}
            />
          </span>
          <span className="tnum w-7 shrink-0 text-right text-[rgb(var(--ink))]">{band.count}</span>
          <span className="tnum w-10 shrink-0 text-right text-[rgb(var(--faint))]">
            {sum ? `${Math.round((band.count / sum) * 100)}%` : "—"}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * One bar, split by status. Reads as a whole with parts, which is the right
 * shape for "what is the posture right now" — a stack of separate bars makes
 * the reader add them up.
 */
export function StatusBar({
  segments,
}: {
  segments: { label: string; count: number; status: Status }[];
}) {
  const total = segments.reduce((n, s) => n + s.count, 0);
  if (!total) return null;

  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-[rgb(var(--raised))]">
        {segments
          .filter((s) => s.count > 0)
          .map((s) => (
            <span
              key={s.label}
              title={`${s.label}: ${s.count}`}
              style={{
                width: `${(s.count / total) * 100}%`,
                backgroundColor: STATUS[s.status].stroke,
              }}
            />
          ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {segments
          .filter((s) => s.count > 0)
          .map((s) => (
            <li key={s.label} className="flex items-center gap-1.5">
              {/* Shape and word as well as colour, the same rule the badges follow. */}
              <span aria-hidden="true" style={{ color: STATUS[s.status].stroke }}>
                {STATUS[s.status].glyph}
              </span>
              <span className="text-[rgb(var(--muted))]">{s.label}</span>
              <span className="tnum text-[rgb(var(--ink))]">{s.count}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}
