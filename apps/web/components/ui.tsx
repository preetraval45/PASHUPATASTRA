/**
 * Console primitives.
 *
 * These exist so that status, time, and emptiness are decided once. When each
 * page invents its own severity colour or its own "nothing here" message, an
 * operator has to re-learn the interface on every screen — and during an
 * incident that reading cost is paid at the worst possible moment.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import type { AttackTechnique } from "@/lib/api";

/* ------------------------------------------------------------------ status */

export type Status = "critical" | "high" | "warning" | "ok" | "neutral";

/**
 * Every status carries a glyph and a word, never colour alone. This covers the
 * colour-blind operator, the monochrome print-out, and the screenshot pasted
 * into a ticket — all of which are ordinary, not edge cases.
 */
export const STATUS: Record<Status, { glyph: string; text: string; ring: string }> = {
  critical: { glyph: "▲", text: "text-[rgb(var(--crit))]", ring: "border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10" },
  high: { glyph: "▲", text: "text-[rgb(var(--high))]", ring: "border-[rgb(var(--high))]/40 bg-[rgb(var(--high))]/10" },
  warning: { glyph: "◆", text: "text-[rgb(var(--warn))]", ring: "border-[rgb(var(--warn))]/40 bg-[rgb(var(--warn))]/10" },
  ok: { glyph: "●", text: "text-[rgb(var(--ok))]", ring: "border-[rgb(var(--ok))]/40 bg-[rgb(var(--ok))]/10" },
  neutral: { glyph: "○", text: "text-[rgb(var(--faint))]", ring: "border-[rgb(var(--edge))] bg-[rgb(var(--raised))]" },
};

export function statusForSeverity(severity: string | null | undefined): Status {
  return (
    ({ critical: "critical", high: "high", medium: "warning", warning: "warning", low: "ok", info: "ok" } as const)[
      severity ?? ""
    ] ?? "neutral"
  );
}

/** Risk bands match the autonomy tiers exactly — a different boundary here
 *  would be a second, contradictory answer to "how dangerous is this?". */
export function statusForRisk(risk: number): Status {
  if (risk <= 30) return "ok";
  if (risk <= 60) return "warning";
  if (risk <= 80) return "high";
  return "critical";
}

export function Badge({
  status = "neutral",
  children,
  className = "",
}: {
  status?: Status;
  children: ReactNode;
  className?: string;
}) {
  const s = STATUS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] uppercase tracking-wide ${s.ring} ${s.text} ${className}`}
    >
      <span aria-hidden="true">{s.glyph}</span>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ layout */

export function Page({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
          {description && (
            <p className="mt-1 max-w-2xl text-sm text-[rgb(var(--muted))]">{description}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      {children}
    </div>
  );
}

export function Panel({
  title,
  aside,
  children,
  className = "",
}: {
  title?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || aside) && (
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-[rgb(var(--edge))] px-4 py-3 sm:px-5">
          {title && <h2 className="label">{title}</h2>}
          {aside && <div className="text-xs text-[rgb(var(--muted))]">{aside}</div>}
        </div>
      )}
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  status,
}: {
  label: string;
  value: string | number;
  hint?: string;
  status?: Status;
}) {
  return (
    <div className="panel p-4">
      <div className="label">{label}</div>
      <div
        className={`tnum mt-2 text-2xl font-semibold ${
          status ? STATUS[status].text : "text-[rgb(var(--ink))]"
        }`}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {hint && <div className="mt-1 text-xs text-[rgb(var(--faint))]">{hint}</div>}
    </div>
  );
}

/**
 * An empty state says what would fill it and how to make that happen. "No data"
 * alone leaves an operator unsure whether the system is quiet or broken — and
 * those need opposite responses.
 */
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="panel p-8 text-center">
      <p className="text-sm text-[rgb(var(--ink))]">{title}</p>
      {children && <div className="mt-2 text-xs text-[rgb(var(--muted))]">{children}</div>}
    </div>
  );
}

export function Offline({ what = "API" }: { what?: string }) {
  return (
    <div className="panel border-[rgb(var(--warn))]/30 bg-[rgb(var(--warn))]/5 p-5">
      <p className="text-sm text-[rgb(var(--warn))]">
        <span aria-hidden="true">◆ </span>
        {what} unreachable
      </p>
      <p className="mt-2 text-xs text-[rgb(var(--muted))]">
        This page shows nothing rather than stale data — during an incident, a number that
        silently stopped updating is worse than no number.
      </p>
      <p className="mt-2 text-xs text-[rgb(var(--faint))]">
        Running locally? Start the API with <code className="mono">uvicorn app.main:app --reload</code>{" "}
        in <code className="mono">services/api</code>.
      </p>
    </div>
  );
}

/* -------------------------------------------------------------------- time */

/** Relative time for recency, absolute in the tooltip for the record. An
 *  operator reasons in "how long ago"; an incident report needs the timestamp. */
export function Ago({ at }: { at: string | null | undefined }) {
  if (!at) return <span className="text-[rgb(var(--faint))]">—</span>;
  const then = new Date(at);
  const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);

  const text =
    seconds < 60
      ? `${Math.floor(seconds)}s ago`
      : seconds < 3600
        ? `${Math.floor(seconds / 60)}m ago`
        : seconds < 86400
          ? `${Math.floor(seconds / 3600)}h ago`
          : `${Math.floor(seconds / 86400)}d ago`;

  return (
    <time dateTime={then.toISOString()} title={then.toLocaleString()} className="tnum">
      {text}
    </time>
  );
}

export function Duration({ seconds }: { seconds: number }) {
  const value =
    seconds < 60
      ? `${Math.round(seconds)}s`
      : seconds < 3600
        ? `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
        : `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return <span className="tnum">{value}</span>;
}

/* ------------------------------------------------------------------- misc */

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="mt-1 text-sm">{children}</dd>
    </div>
  );
}

/** Identifiers an operator might paste into a terminal are always monospace. */
export function Ident({ children }: { children: ReactNode }) {
  return <span className="mono text-[rgb(var(--astra))]">{children}</span>;
}

/**
 * Evidence citations, as links.
 *
 * They used to be plain text. An id a reader cannot follow is decoration: it
 * looks checkable, so it gets taken on trust, and a fabricated reference reads
 * exactly like a real one. Following it is the only thing that makes the
 * grounding rule mean anything from outside the code.
 */
export function Evidence({ refs }: { refs: string[] }) {
  if (!refs.length) return null;
  return (
    <p className="mono mt-1 text-[11px] text-[rgb(var(--faint))]">
      evidence:{" "}
      {refs.map((ref, index) => (
        <span key={ref}>
          {index > 0 && ", "}
          <Link
            href={`/evidence/${encodeURIComponent(ref)}`}
            className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
          >
            {ref}
          </Link>
        </span>
      ))}
    </p>
  );
}

/**
 * The ATT&CK mapping for a causal step, set as quietly as the evidence line
 * beneath it: this is a citation, not a finding, and giving it the weight of a
 * finding would make every step look like a conclusion.
 *
 * The id links to the catalogue. A reader who does not recognise `T1110.004`
 * can go and read what it is, which is the entire reason for using a shared
 * vocabulary instead of a sentence someone wrote.
 */
export function Technique({ technique }: { technique: AttackTechnique | null }) {
  if (!technique) return null;
  const [id, sub] = technique.id.split(".");
  return (
    <p className="mt-1 text-[11px] text-[rgb(var(--faint))]">
      <span className="mono">technique: </span>
      <a
        href={`https://attack.mitre.org/techniques/${sub ? `${id}/${sub}` : id}/`}
        target="_blank"
        rel="noreferrer"
        className="focusable mono rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
      >
        {technique.id}
      </a>{" "}
      {technique.name} · {technique.tactic}
    </p>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]" />
      ))}
    </div>
  );
}
