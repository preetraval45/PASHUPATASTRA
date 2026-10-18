"use client";

/**
 * The console's frame (RP-48): a sidebar, a slim top bar, and a working area
 * that fills the rest of the window.
 *
 * It replaced a website header over a centred column, which made every console
 * page read as a document. An operator moves between the same nine places all
 * day; those belong in a rail that is always there, grouped by what the
 * operator is doing, with the working area free to be as tall as the window.
 *
 * Collapsible to icons (remembered per browser), and a drawer below `lg`, where
 * a permanent rail would take a third of a phone.
 */

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";

import { Attribution } from "@/components/attribution";
import { Mark, Sigil } from "@/components/chrome";
import { Search } from "@/components/search";
import { ThemeToggle } from "@/components/theme";

type Item = { href: string; label: string; icon: keyof typeof ICONS; hint?: string; exact?: boolean };

/**
 * One rail for the whole site since the owner's review of RP-48: the public
 * pages and the console had become two products with two headers, and moving
 * between them felt like leaving. Grouped by what a person is doing — finding
 * their feet, operating, analysing, responding, governing, learning.
 */
const SECTIONS: { title: string; items: Item[] }[] = [
  {
    title: "Start",
    items: [
      { href: "/", label: "Home", icon: "home", exact: true },
      { href: "/how-it-works", label: "How it works", icon: "book" },
    ],
  },
  {
    title: "Operate",
    items: [
      { href: "/overview", label: "Overview", icon: "grid" },
      { href: "/incidents", label: "Incidents", icon: "alert" },
      // "Sati AI" is the owner's name for the page. The sub-label is BRAND.md's
      // rule that a page's first mention of Sati says what it is, because the
      // bare word has an unrelated common meaning in English.
      { href: "/ask", label: "Sati AI", icon: "chat", hint: "investigation agent" },
      { href: "/observatory", label: "Observatory", icon: "radar" },
    ],
  },
  {
    title: "Analyze",
    items: [
      { href: "/analytics", label: "Analytics", icon: "chart" },
      { href: "/models", label: "Sati models", icon: "cube", hint: "nine, trained on real data" },
    ],
  },
  {
    title: "Respond",
    items: [
      { href: "/actions", label: "Actions", icon: "bolt" },
      { href: "/detections", label: "Detections", icon: "shield" },
      { href: "/attack", label: "ATT&CK coverage", icon: "matrix" },
    ],
  },
  {
    title: "Govern",
    items: [
      { href: "/audit", label: "Audit trail", icon: "ledger" },
      { href: "/infrastructure", label: "Infrastructure", icon: "network" },
    ],
  },
  {
    title: "Learn",
    items: [
      { href: "/training", label: "Training", icon: "cap", hint: "cyber defence practice" },
      { href: "/evaluation", label: "Evaluation", icon: "check" },
    ],
  },
];

/** Secondary pages, at the foot of the rail rather than in a section. */
const FOOTER: Item[] = [
  { href: "/impact", label: "Impact", icon: "pulse" },
  { href: "/press", label: "Press", icon: "news" },
];

function isCurrent(item: Item, pathname: string): boolean {
  if (item.exact) return pathname === item.href;
  if (item.href === "/training") return pathname.startsWith("/training") || pathname.startsWith("/blue-team");
  return pathname.startsWith(item.href);
}

const STORAGE_KEY = "pashu.sidebar";

export function ConsoleFrame({ status, children }: { status: ReactNode; children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(STORAGE_KEY) === "collapsed");
    } catch {
      // Storage can be blocked; an expanded rail is the safe default.
    }
  }, []);

  // Navigating closes the drawer, or it stays open over the page it opened.
  useEffect(() => setDrawer(false), [pathname]);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setDrawer(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  const toggle = () =>
    setCollapsed((was) => {
      try {
        localStorage.setItem(STORAGE_KEY, was ? "expanded" : "collapsed");
      } catch {
        // Not remembered; still toggled.
      }
      return !was;
    });

  return (
    <div className="flex h-dvh overflow-hidden bg-[rgb(var(--ground))]">
      {/* The rail, from `lg` up. */}
      <aside
        data-sidebar
        data-collapsed={collapsed ? "" : undefined}
        className={`hidden shrink-0 border-r border-[rgb(var(--edge))] bg-[rgb(var(--panel))] transition-[width] duration-200 lg:flex lg:flex-col ${
          collapsed ? "w-[4.25rem]" : "w-64"
        }`}
      >
        <Rail pathname={pathname} collapsed={collapsed} onToggle={toggle} />
      </aside>

      {/* The drawer, below `lg`. */}
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setDrawer(false)}
            className="absolute inset-0 bg-black/50"
          />
          <aside className="rise absolute inset-y-0 left-0 flex w-72 flex-col border-r border-[rgb(var(--edge))] bg-[rgb(var(--panel))] shadow-2xl">
            <Rail pathname={pathname} collapsed={false} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))]/90 px-3 backdrop-blur sm:px-5">
          <button
            type="button"
            onClick={() => setDrawer(true)}
            aria-label="Open navigation"
            className="focusable inline-flex h-9 w-9 items-center justify-center rounded-md border border-[rgb(var(--edge))] text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))] lg:hidden"
          >
            <Icon name="menu" />
          </button>
          <Link href="/" className="focusable shrink-0 rounded lg:hidden">
            <Sigil className="h-7 w-auto" />
          </Link>
          <p className="hidden text-sm font-medium text-[rgb(var(--muted))] lg:block">
            {titleFor(pathname)}
          </p>
          <div className="ml-auto flex min-w-0 items-center gap-x-3">
            <Suspense fallback={null}>
              <Search />
            </Suspense>
            {status}
            <ThemeToggle />
          </div>
        </header>

        {children}
      </div>
    </div>
  );
}

function Rail({
  pathname,
  collapsed,
  onToggle,
}: {
  pathname: string;
  collapsed: boolean;
  onToggle?: () => void;
}) {
  return (
    <>
      <div className={`flex h-14 shrink-0 items-center border-b border-[rgb(var(--edge))] ${collapsed ? "justify-center" : "px-4"}`}>
        <Link href="/" className="focusable rounded" title="Pashupatastra — home">
          {collapsed ? <Mark /> : <Sigil className="h-8 w-auto" />}
        </Link>
      </div>

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-2.5 py-4">
        {SECTIONS.map((section) => (
          <div key={section.title} className="mb-5 last:mb-0">
            {collapsed ? (
              <div className="mx-auto mb-2 h-px w-6 bg-[rgb(var(--edge))]" aria-hidden="true" />
            ) : (
              <p className="label mb-1.5 px-2.5">{section.title}</p>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.href}>
                  <RailLink item={item} current={isCurrent(item, pathname)} collapsed={collapsed} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 space-y-0.5 border-t border-[rgb(var(--edge))] px-2.5 py-3">
        {FOOTER.map((item) => (
          <RailLink key={item.href} item={item} current={isCurrent(item, pathname)} collapsed={collapsed} />
        ))}
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`focusable flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm text-[rgb(var(--faint))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))] ${
              collapsed ? "justify-center" : ""
            }`}
          >
            <Icon name={collapsed ? "expand" : "collapse"} />
            {!collapsed && <span>Collapse</span>}
          </button>
        )}
        {/* The credit is one line and belongs on every page (testbuildinfo);
            the console has no footer, so it lives at the foot of the rail. */}
        {!collapsed && (
          <p className="flex flex-wrap gap-x-3 gap-y-1 px-2.5 pt-2 text-[11px] text-[rgb(var(--faint))]">
            <Attribution />
          </p>
        )}
      </div>
    </>
  );
}

function RailLink({ item, current, collapsed }: { item: Item; current: boolean; collapsed: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={current ? "page" : undefined}
      title={collapsed ? item.label : undefined}
      className={`focusable group relative flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition ${
        collapsed ? "justify-center" : ""
      } ${
        current
          ? "bg-[rgb(var(--astra))]/10 text-[rgb(var(--ink))]"
          : "text-[rgb(var(--muted))] hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
      }`}
    >
      {current && (
        <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-[rgb(var(--astra))]" />
      )}
      <span className={current ? "text-[rgb(var(--astra))]" : "text-[rgb(var(--faint))] group-hover:text-[rgb(var(--ink))]"}>
        <Icon name={item.icon} />
      </span>
      {collapsed ? (
        <span className="sr-only">
          {item.label}
          {item.hint && `, ${item.hint}`}
        </span>
      ) : (
        <span className="min-w-0">
          <span className="block truncate">{item.label}</span>
          {item.hint && (
            <span className="block truncate text-[10.5px] leading-tight text-[rgb(var(--faint))]">{item.hint}</span>
          )}
        </span>
      )}
      <Pending />
    </Link>
  );
}

/** A dot beside the link that was clicked while the next page renders (R100). */
function Pending() {
  const { pending } = useLinkStatus();
  if (!pending) return null;
  return (
    <span role="status" aria-label="Loading" className="ml-auto">
      <span aria-hidden="true" className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[rgb(var(--astra))]" />
    </span>
  );
}

function titleFor(pathname: string): string {
  for (const item of [...SECTIONS.flatMap((section) => section.items), ...FOOTER]) {
    if (isCurrent(item, pathname)) return item.label;
  }
  if (pathname.startsWith("/entity")) return "Entity";
  if (pathname.startsWith("/evidence")) return "Evidence";
  if (pathname.startsWith("/search")) return "Search";
  return "Console";
}

/** Line icons, 20px, drawn on a 24 grid with the current colour. Inline so the
 *  console pulls no icon font or library. */
const ICONS = {
  grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  alert: "M12 3 2.5 20h19L12 3zM12 10v4M12 17.5v.01",
  chat: "M4 5h16v11H9l-5 4V5zM8 9.5h8M8 12.5h5",
  radar: "M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M12 12l5.5-5.5",
  bolt: "M13 2 4 14h7l-1 8 9-12h-7l1-8z",
  shield: "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3zM9 12l2 2 4-4",
  matrix: "M3 4h18v16H3zM3 9.3h18M3 14.6h18M9 4v16M15 4v16",
  ledger: "M6 3h12v18H6zM9 7h6M9 11h6M9 15h4",
  network: "M12 5m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M5 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M19 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M12 7v4M12 11l-6 5.5M12 11l6 5.5",
  target: "M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0M12 12m-4.5 0a4.5 4.5 0 1 0 9 0a4.5 4.5 0 1 0-9 0M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0",
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zM4 19a2 2 0 0 1 2-2h13",
  home: "M3 11 12 4l9 7M5 10v10h5v-6h4v6h5V10",
  collapse: "M15 6l-6 6 6 6M5 4v16",
  expand: "M9 6l6 6-6 6M19 4v16",
  menu: "M4 7h16M4 12h16M4 17h16",
  cube: "M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3zM12 12l8-4.5M12 12v9M12 12L4 7.5",
  chart: "M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3M20 16V6",
  cap: "M2 9l10-5 10 5-10 5L2 9zM6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5M22 9v6",
  check: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M8 12l3 3 5-6",
  pulse: "M3 12h4l3-7 4 14 3-7h4",
  news: "M4 5h13v14H6a2 2 0 0 1-2-2V5zM17 9h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5M8 17h3",
} as const;

export function Icon({ name, className = "h-5 w-5" }: { name: keyof typeof ICONS; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d={ICONS[name]} />
    </svg>
  );
}
