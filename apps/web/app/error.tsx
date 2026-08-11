"use client";

/**
 * States what broke rather than showing a blank page, and never falls back to
 * cached numbers: a stale figure presented as current is worse than an honest
 * gap, because the operator cannot tell it is stale.
 */
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="panel border-[rgb(var(--crit))]/30 bg-[rgb(var(--crit))]/5 p-6">
      <h1 className="text-lg text-[rgb(var(--crit))]">
        <span aria-hidden="true">▲ </span>This view failed to render
      </h1>
      <p className="mt-2 text-sm text-[rgb(var(--muted))]">
        Nothing on screen is stale — the page stopped rather than showing old data.
      </p>
      <pre className="mono mt-4 overflow-x-auto rounded border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-3 text-xs text-[rgb(var(--muted))]">
        {error.message}
      </pre>
      <button
        onClick={reset}
        className="focusable mt-4 rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
      >
        Retry
      </button>
    </div>
  );
}
