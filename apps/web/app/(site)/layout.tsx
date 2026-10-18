import Link from "next/link";
import { Suspense } from "react";

import { Attribution } from "@/components/attribution";
import { ModeIndicator, Sigil } from "@/components/chrome";
import { ShortcutsButton } from "@/components/keys";
import { Nav } from "@/components/nav";
import { Search } from "@/components/search";
import { ThemeToggle } from "@/components/theme";
import { getHealth } from "@/lib/api";

/**
 * The public site: the landing page and the pages a visitor reads to decide
 * whether the thing is real. A header and a footer around a readable column.
 *
 * The console has its own shell (`(console)/layout.tsx`). The way across is the
 * one primary button in this header — "Open the console" — rather
 * than seven console tabs a newcomer has no context for yet.
 */
export default async function SiteLayout({ children }: { children: React.ReactNode }) {
  const health = await getHealth();

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))]/90 backdrop-blur">
        <div className="relative mx-auto flex max-w-[100rem] items-center gap-x-3 px-4 py-2.5 sm:gap-x-4 sm:px-6 sm:py-3">
          <Link href="/" className="focusable shrink-0 rounded">
            <Sigil />
          </Link>

          <Nav status={<ModeIndicator health={health} />} />

          <div className="ml-auto flex min-w-0 items-center gap-x-3">
            <Suspense fallback={null}>
              <Search />
            </Suspense>
            <div className="hidden nav:flex nav:items-center nav:gap-x-3">
              <ModeIndicator health={health} />
            </div>
            <ThemeToggle />
            <Link
              href="/overview"
              data-open-console
              className="focusable hidden shrink-0 rounded-md bg-[rgb(var(--astra))] px-3.5 py-2 text-sm font-medium text-[rgb(var(--ground))] shadow-sm transition hover:brightness-110 sm:inline-flex"
            >
              Open the console
            </Link>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
        {children}
      </main>

      <footer className="mx-auto max-w-7xl px-4 pb-10 text-xs text-[rgb(var(--faint))] sm:px-6">
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span>Observe. Reason. Act. Verify.</span>
          <Link href="/overview" className="focusable rounded hover:text-[rgb(var(--muted))]">
            Console
          </Link>
          <Link href="/ask" className="focusable rounded hover:text-[rgb(var(--muted))]">
            Ask
          </Link>
          <ShortcutsButton />
          <Attribution />
        </span>
      </footer>
    </>
  );
}
