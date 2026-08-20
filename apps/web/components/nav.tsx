"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/incidents", label: "Incidents" },
  { href: "/infrastructure", label: "Infrastructure" },
  { href: "/actions", label: "Actions" },
  { href: "/audit", label: "Audit" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className="-mx-1 flex min-w-0 gap-1 overflow-x-auto text-sm [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {NAV.map((item) => {
        // Exact match for the root, prefix match elsewhere, so a detail page
        // still shows its section as current.
        const current = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className={`focusable shrink-0 rounded px-3 py-1.5 transition-colors ${
              current
                ? "bg-[rgb(var(--raised))] text-[rgb(var(--ink))]"
                : "text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
