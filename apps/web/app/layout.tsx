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

/** Arrow + trident geometry + closed loop. Geometric, not illustrative. */
function Sigil() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9.5" stroke="rgb(var(--astra))" strokeOpacity="0.45" />
      <path d="M12 3.5v17" stroke="rgb(var(--astra))" strokeWidth="1.4" />
      <path d="M7.5 8.5v4M16.5 8.5v4" stroke="rgb(var(--astra))" strokeWidth="1.4" />
      <path d="M8.6 6.2 12 2.8l3.4 3.4" stroke="rgb(var(--astra))" strokeWidth="1.4" />
    </svg>
  );
}
