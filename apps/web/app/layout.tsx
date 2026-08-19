import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Live } from "@/components/live";
import { Nav } from "@/components/nav";
import { Search } from "@/components/search";
import { ThemeToggle, themeScript } from "@/components/theme";
import { getHealth } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pashupatastra",
  description: "Autonomous intelligence for complex systems. Observe. Reason. Act. Verify.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const health = await getHealth();

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Before first paint: a flash of the wrong theme on every navigation
            makes a tool feel unreliable. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
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
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
            <Link href="/" className="focusable flex items-center gap-3 rounded">
              <Sigil />
              <span className="text-sm font-semibold tracking-[0.18em]">
                <span className="sm:hidden">PASHU</span>
                <span className="hidden sm:inline">PASHUPATASTRA</span>
              </span>
            </Link>
            <Nav />
            <div className="flex w-full items-center gap-3 sm:ml-auto sm:w-auto">
              <Suspense fallback={null}>
                <Search />
              </Suspense>
              <ModeIndicator health={health} />
              <Live />
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main id="main" className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>

        <footer className="mx-auto max-w-7xl px-4 pb-10 text-xs text-[rgb(var(--faint))] sm:px-6">
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
      <span className="flex items-center gap-2 text-xs text-[rgb(var(--warn))]">
        <span aria-hidden="true">◆</span> API unreachable
      </span>
    );
  }

  const live = !health.dry_run;
  return (
    <div className="flex items-center gap-3 text-xs sm:gap-4">
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
 * The mark.
 *
 * An <img> rather than inline geometry, so it cannot inherit theme colour — the
 * artwork carries its own palette in both themes. Two things to know before
 * changing it:
 *
 *   - It must read at 32px. `logo.webp` is the full spear drawn corner to
 *     corner on a square canvas: 5% of its pixels are ink, spread along a
 *     diagonal, so at this size it is a hairline. `mark.webp` is the head
 *     alone, which survives the size. Swap that one file to change the mark.
 *   - Its crimson sits close to --crit, which in this interface means live
 *     execution and critical severity. The mark is therefore kept out of the
 *     status region of the chrome and never placed beside a severity badge.
 *
 * Canonical artwork: public/logo.webp. See docs/BRAND.md.
 */
function Sigil() {
  return (
    <img
      src="/mark.webp"
      alt=""
      width={32}
      height={32}
      className="h-8 w-8 shrink-0 object-contain"
      aria-hidden="true"
    />
  );
}
