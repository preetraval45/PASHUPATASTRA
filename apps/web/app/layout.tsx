import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { Live } from "@/components/live";
import { Nav } from "@/components/nav";
import { Search } from "@/components/search";
import { ThemeToggle, themeScript } from "@/components/theme";
import { getHealth } from "@/lib/api";
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
  const health = await getHealth();

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
        <a
          href="#main"
          className="focusable sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[rgb(var(--raised))] focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>

        <header className="sticky top-0 z-40 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))]/95 backdrop-blur">
          {/* The chrome is wider than the content it sits above. `max-w-7xl`
              capped this at 1280px on every screen, so the status group — 804px
              of it — always wrapped to a second row and the header stood 111px
              tall on a 1920px display with most of that width unused.

              One row from `xl` up, where everything genuinely fits, and two
              rows below it. Forcing one row earlier starved the nav: the search
              and the status chips held their width while the nav collapsed to
              nothing, and between 640 and 1280 not one tab was fully visible.
              Navigation is the last thing a header should give up, so the nav
              never shrinks and the status group wraps instead. */}
          <div className="mx-auto flex max-w-[100rem] flex-wrap items-center gap-x-4 gap-y-2.5 px-4 py-2.5 sm:px-6 sm:py-3 xl:flex-nowrap">
            <Link href="/" className="focusable shrink-0 rounded">
              <Sigil />
            </Link>
            <Nav />
            <div className="flex w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-2 sm:ml-auto sm:w-auto xl:shrink-0 xl:flex-nowrap">
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
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs sm:gap-x-4">
      {health.status !== "ok" && (
        <span
          className="text-[rgb(var(--warn))]"
          title="Nothing is written to a database. Incidents, approvals and the audit log live in the server process and are lost when it restarts."
        >
          <span aria-hidden="true">◆</span> memory only
        </span>
      )}
      <span className="text-[rgb(var(--faint))]" title="Which environment this deployment reports itself as.">
        env {health.environment}
      </span>
      <span
        className={
          live
            ? "rounded border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 px-2 py-0.5 text-[rgb(var(--crit))]"
            : "rounded border border-[rgb(var(--edge))] px-2 py-0.5 text-[rgb(var(--muted))]"
        }
      >
        {/* The base text is one node and the qualifier is a separate optional
            one — never two copies of the same words behind breakpoints, which
            is how the wordmark came to read PASHUPASHUPATASTRA. Below xl the
            row has no space for the qualifier and the title still carries it. */}
        {live ? "LIVE EXECUTION" : "dry run"}
        {!live && <span className="hidden xl:inline"> · nothing executes</span>}
      </span>
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
