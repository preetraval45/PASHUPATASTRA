import type { Metadata } from "next";
import Link from "next/link";

import { Nav } from "@/components/nav";
import { getHealth } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pashupatastra",
  description: "Autonomous intelligence for complex systems. Observe. Reason. Act. Verify.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const health = await getHealth();

  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        {/* Keyboard operators are faster than mouse operators during an
            incident, and this is the first thing they reach for. */}
        <a
          href="#main"
          className="focusable sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[rgb(var(--raised))] focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>

        <header className="sticky top-0 z-40 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))]/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-6 py-3">
            <Link href="/" className="focusable flex items-center gap-3 rounded">
              <Sigil />
              <span className="text-sm font-semibold tracking-[0.18em]">PASHUPATASTRA</span>
            </Link>
            <Nav />
            <ModeIndicator health={health} />
          </div>
        </header>

        <main id="main" className="mx-auto max-w-7xl px-6 py-10">
          {children}
        </main>

        <footer className="mx-auto max-w-7xl px-6 pb-10 text-xs text-[rgb(var(--faint))]">
          Observe. Reason. Act. Verify.
        </footer>
      </body>
    </html>
  );
}

/**
 * Execution mode is in the chrome, on every page, because it is the single most
 * consequential fact about the system: whether an approval will change
 * production or only describe what it would have changed. Burying it on a
 * settings screen is how someone learns the answer the hard way.
 */
function ModeIndicator({
  health,
}: {
  health: Awaited<ReturnType<typeof getHealth>>;
}) {
  if (!health) {
    return (
      <span className="ml-auto flex items-center gap-2 text-xs text-[rgb(var(--warn))]">
        <span aria-hidden="true">◆</span> API unreachable
      </span>
    );
  }

  const live = !health.dry_run;
  return (
    <div className="ml-auto flex items-center gap-4 text-xs">
      {health.status !== "ok" && (
        <span
          className="text-[rgb(var(--warn))]"
          title="The audit trail or incident store is not durable — it will not survive a restart."
        >
          <span aria-hidden="true">◆</span> degraded
        </span>
      )}
      <span className="text-[rgb(var(--faint))]">{health.environment}</span>
      <span
        className={
          live
            ? "rounded border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 px-2 py-0.5 text-[rgb(var(--crit))]"
            : "rounded border border-[rgb(var(--edge))] px-2 py-0.5 text-[rgb(var(--muted))]"
        }
      >
        {live ? "LIVE EXECUTION" : "dry run"}
      </span>
    </div>
  );
}

/**
 * The mark: closed loop, arrow in flight, decision node, trident head.
 * Inlined rather than an <img> so it inherits colour and stays crisp.
 * Canonical source of the same geometry: public/mark.svg
 */
function Sigil() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 64 64"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="32" cy="32" r="27" stroke="rgb(var(--astra))" strokeOpacity="0.38" strokeWidth="1.5" />
      <g stroke="rgb(var(--astra))" strokeOpacity="0.55" strokeWidth="1.5">
        <path d="M6 24 L14 30" />
        <path d="M6 40 L14 34" />
        <path d="M13 22 L19 29" />
        <path d="M13 42 L19 35" />
      </g>
      <path d="M12 32 H44" stroke="rgb(var(--astra))" strokeWidth="2.25" />
      <g stroke="rgb(var(--gold))" strokeWidth="1.6">
        <path d="M28 32 H36" />
        <path d="M32 28 V36" />
        <path d="M29.2 29.2 L34.8 34.8" />
        <path d="M34.8 29.2 L29.2 34.8" />
      </g>
      <g stroke="rgb(var(--gold))" strokeWidth="2.25">
        <path d="M44 23 V41" />
        <path d="M44 23 L53.5 29.5" />
        <path d="M44 32 H58" />
        <path d="M44 41 L53.5 34.5" />
      </g>
    </svg>
  );
}
