import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pashupatastra",
  description: "Autonomous intelligence for complex systems. Observe. Reason. Act. Verify.",
};

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/incidents", label: "Incidents" },
  { href: "/infrastructure", label: "Infrastructure" },
  { href: "/actions", label: "Actions" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="border-b border-[rgb(var(--edge))]">
          <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-4">
            <Link href="/" className="flex items-center gap-3">
              <Sigil />
              <span className="text-sm font-semibold tracking-[0.2em]">PASHUPATASTRA</span>
            </Link>
            <nav className="flex gap-6 text-sm text-[rgb(var(--muted))]">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} className="hover:text-[rgb(var(--ink))]">
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 pb-10 text-xs text-[rgb(var(--muted))]">
          Observe. Reason. Act. Verify. — Phase 0 preview, dry-run by default.
        </footer>
      </body>
    </html>
  );
}

/**
 * The mark: closed loop, arrow in flight, decision node, trident head.
 * Inlined rather than an <img> so it inherits colour and stays crisp at 26px.
 * Canonical source of the same geometry: public/mark.svg
 */
function Sigil() {
  return (
    <svg
      width="26"
      height="26"
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
