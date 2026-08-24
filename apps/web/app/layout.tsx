import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { Attribution } from "@/components/attribution";
import { Nav } from "@/components/nav";
import { CommandPalette } from "@/components/palette";
import { Search } from "@/components/search";
import { ThemeToggle, themeScript } from "@/components/theme";
import { getHealth, getSearchIndex } from "@/lib/api";
import { SITE } from "@/lib/site";
import "./globals.css";

/**
 * The pairing: Inter for prose, JetBrains Mono for anything an operator might
 * retype or paste.
 *
 * Inter because this is a dense data interface and it was already assumed —
 * `globals.css` has been asking for `cv02`/`cv03`/`cv04` since it was written,
 * and those are Inter character variants, so they have been inert on a system
 * font this whole time.
 *
 * JetBrains Mono for a functional reason rather than taste: the monospace here
 * carries event ids, IP addresses and technique codes, and it has a slashed
 * zero and unambiguous `1`/`l`/`I`. Misreading `SEC-0001-l` costs an operator
 * more than a typeface preference is worth.
 *
 * Loaded through `next/font`, which self-hosts them at build time. A visitor's
 * browser makes no request to Google — a security console that reports every
 * page view to a third party is a poor advertisement for itself, and `display:
 * swap` means text is readable before the face arrives rather than invisible.
 */
const sans = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

const DESCRIPTION =
  "A security incident-response console: detections become diagnoses, diagnoses are " +
  "challenged by evidence, and every response is scored and tiered before anyone acts.";

export const metadata: Metadata = {
  /* Relative URLs in Open Graph tags are not fetched, and a sitemap of relative
     paths is rejected outright. `metadataBase` is what makes the rest of this
     file able to use paths. */
  metadataBase: new URL(SITE),
  title: {
    default: "Pashupatastra",
    /* Every page appends this, so a browser full of tabs during an incident
       stays navigable and a search result says which page it is. */
    template: "%s · Pashupatastra",
  },
  description: DESCRIPTION,
  applicationName: "Pashupatastra",
  openGraph: {
    type: "website",
    siteName: "Pashupatastra",
    title: "Pashupatastra",
    description: DESCRIPTION,
    url: SITE,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Pashupatastra" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Pashupatastra",
    description: DESCRIPTION,
    images: ["/og.png"],
  },
  /* Every icon, listed. Declaring `icons` at all replaces Next's file-convention
     detection rather than adding to it, so a partial list silently dropped the
     512px icon and the apple-touch link — both were being generated and neither
     was referenced. `sizes: "any"` on the .ico because it carries 16, 32 and 48
     and naming one of them tells a browser the others are not there. */
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-48x48.png", sizes: "48x48", type: "image/png" },
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
      { url: "/icon.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

/** Painted by the browser around the page — the address bar on Android, the
 *  window chrome of an installed app. Left as the dark ground because that is
 *  what this console opens as. */
export const viewport = {
  themeColor: "#0b0d11",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Both in parallel. The palette's index is fetched here, on the server, so
  // that filtering it later costs a keystroke rather than a round trip.
  const [health, searchIndex] = await Promise.all([getHealth(), getSearchIndex()]);

  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        {/* Before first paint: a flash of the wrong theme on every navigation
            makes a tool feel unreliable. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen antialiased">
        {/* Keyboard operators are faster than mouse operators during an
            incident, and this is the first thing they reach for. */}
        {/* Rendered on every page, so Ctrl-K works from every page. Returns
            null until opened, so it costs nothing until it is wanted. */}
        <CommandPalette index={searchIndex} />

        <a
          href="#main"
          className="focusable sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[rgb(var(--raised))] focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>

        <header className="sticky top-0 z-40 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))]/95 backdrop-blur">
          {/* One row at every width. The previous version wrapped below `xl`
              and gave the nav an `overflow-x-auto` strip with the scrollbar
              hidden — which put five links behind a gesture nobody could see,
              and left a mouse user at 768px unable to reach Incidents at all.

              Now the row never wraps and each group has a width where it steps
              aside instead: the links become a menu below `lg`, the search
              becomes an icon below `sm`, and the freshness clock drops at `xl`.
              Navigation and execution mode are the two things that never
              disappear — they move into the menu, which is a place, rather than
              into an overflow, which is not. */}
          <div className="relative mx-auto flex max-w-[100rem] items-center gap-x-3 px-4 py-2.5 sm:gap-x-4 sm:px-6 sm:py-3">
            <Link href="/" className="focusable shrink-0 rounded">
              <Sigil />
            </Link>

            <Nav status={<ModeIndicator health={health} />} />

            {/* `ml-auto` here and on the menu button, so exactly one of them
                claims the gap depending on which is showing. */}
            <div className="ml-auto flex min-w-0 items-center gap-x-3">
              <Suspense fallback={null}>
                <Search />
              </Suspense>
              <div className="hidden lg:flex lg:items-center lg:gap-x-3">
                <ModeIndicator health={health} />
              </div>
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main id="main" className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>

        <footer className="mx-auto max-w-7xl px-4 pb-10 text-xs text-[rgb(var(--faint))] sm:px-6">
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>Observe. Reason. Act. Verify.</span>
            {/* Reachable from anywhere without taking a navigation slot. R52's
                rule is that a tab is for something a visitor goes looking for;
                "how it works" is something they go looking for *after* a claim,
                which is here and on the landing page. */}
            <Link href="/how-it-works" className="focusable rounded hover:text-[rgb(var(--muted))]">
              How it works
            </Link>
            <Attribution />
          </span>
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
  const degraded = health.status !== "ok";

  // Silent when the answer is boring.
  //
  // This used to show `env dev · dry run · nothing executes` on every page of
  // a deployment that is permanently in dry run, and a warning that is always
  // present is one nobody reads. The fact it carries — whether an approval
  // would change production — matters enormously in one state and not at all
  // in the other, so it is shown in one state and not the other.
  //
  // Not a removal: LIVE EXECUTION is louder now than it was when it sat in a
  // row of grey chips being ignored.
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
 * how the header ended up reading `PASHUPASHUPATASTRA` (R1). The accessible
 * name and the text a crawler sees both come from `alt`, which is the one place
 * this name should live now.
 *
 * `logo.webp` is a derivative — `scripts/buildbrand.py` builds it from
 * `logo.png` by removing the baked-in white outline and the transparent
 * margin. The outline is drawn for a light page and reads as a sticker edge
 * on this one; the margin was 400 KB of nothing on every page load. Edit the
 * PNG and re-run the script — never edit the WebP.
 */
function Sigil() {
  return (
    <img
      src="/logo.webp"
      alt="Pashupatastra"
      width={1101}
      height={363}
      className="h-8 w-auto sm:h-10"
    />
  );
}
