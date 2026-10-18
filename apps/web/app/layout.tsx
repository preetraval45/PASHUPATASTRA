import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ShortcutsProvider } from "@/components/keys";
import { CommandPalette } from "@/components/palette";
import { themeScript } from "@/components/theme";
import { getSearchIndex } from "@/lib/api";
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

/**
 * What every page shares, whichever shell it sits in.
 *
 * The chrome itself lives one level down since RP-48: `(site)/layout.tsx` is
 * the public site's header and footer, and `(console)/layout.tsx` is the app —
 * a sidebar and a working area that fills the window. Route groups, so no URL
 * changed.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Fetched here, on the server, so that filtering the palette later costs a
  // keystroke rather than a round trip.
  const searchIndex = await getSearchIndex();

  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        {/* Before first paint: a flash of the wrong theme on every navigation
            makes a tool feel unreliable. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen antialiased">
        <ShortcutsProvider>
          {/* On every page, so Ctrl-K works from every page. Returns null until
              opened, so it costs nothing until it is wanted. */}
          <CommandPalette index={searchIndex} />

          <a
            href="#main"
            className="focusable sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[rgb(var(--raised))] focus:px-3 focus:py-2 focus:text-sm"
          >
            Skip to content
          </a>

          {children}
        </ShortcutsProvider>
      </body>
    </html>
  );
}
