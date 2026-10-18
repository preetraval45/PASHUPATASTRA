/**
 * Pieces of chrome shared by the two shells: the public site's header and the
 * console's sidebar. Moved out of `app/layout.tsx` when the console became an
 * app (RP-48), so both shells say the same thing about execution mode.
 */

import type { getHealth } from "@/lib/api";

/**
 * Execution mode is in the chrome, on every page, because it is the single most
 * consequential fact about the system: whether an approval will change
 * production or only describe what it would have changed. Burying it on a
 * settings screen is how someone learns the answer the hard way.
 *
 * Silent when the answer is boring. A warning that is always present is one
 * nobody reads, so `dry run` — the permanent state of the public deployment —
 * shows nothing, and LIVE EXECUTION is loud when it is true.
 */
export function ModeIndicator({
  health,
}: {
  health: Awaited<ReturnType<typeof getHealth>>;
}) {
  if (!health) {
    return (
      <span className="flex items-center gap-2 text-xs text-[rgb(var(--warn))]">
        <span aria-hidden="true">◆</span> API unreachable
      </span>
    );
  }

  const live = !health.dry_run;
  const degraded = health.status !== "ok";
  if (!live && !degraded) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 whitespace-nowrap text-xs sm:gap-x-4">
      {degraded && (
        <span
          className="text-[rgb(var(--warn))]"
          title="Nothing is written to a database. Incidents, approvals and the audit log live in the server process and are lost when it restarts."
        >
          <span aria-hidden="true">◆</span> memory only
        </span>
      )}
      {live && (
        <span className="rounded border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 px-2 py-0.5 text-[rgb(var(--crit))]">
          <span aria-hidden="true">▲</span> LIVE EXECUTION
          <span className="hidden xl:inline"> · env {health.environment}</span>
        </span>
      )}
    </div>
  );
}

/**
 * The lockup: the wordmark and the spear, as one piece of artwork.
 *
 * The name is *in* the image, so it is not also set as text beside it — that is
 * how the header ended up reading `PASHUPASHUPATASTRA` (R1). `logo.webp` is
 * built by `scripts/buildbrand.py`; edit the PNG and re-run it, never the WebP.
 */
export function Sigil({ className = "h-8 w-auto sm:h-10" }: { className?: string }) {
  return (
    <img src="/logo.webp" alt="Pashupatastra" width={1101} height={363} className={className} />
  );
}

/**
 * The square mark alone, for the collapsed sidebar where the lockup does not
 * fit. 32px is BRAND.md's floor for the artwork in chrome.
 */
export function Mark() {
  return (
    <img src="/icon.png" alt="Pashupatastra" width={32} height={32} className="h-8 w-8 rounded" />
  );
}
