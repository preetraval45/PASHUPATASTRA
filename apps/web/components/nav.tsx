"use client";

/**
 * Primary navigation.
 *
 * Five links do not fit beside a search box and a status group on anything
 * narrower than a laptop, and the previous attempt to make them fit was an
 * `overflow-x-auto` strip with the scrollbar hidden. Nothing was missing from
 * the DOM, which is why the layout checks passed — but at 768px only "Overview"
 * was on screen, with no scrollbar, no fade, and no affordance of any kind. A
 * visitor with a mouse simply could not reach Incidents.
 *
 * So the links are a row when there is room for a row, and a menu when there is
 * not. A menu is more clicks; unreachable navigation is infinite clicks.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/incidents", label: "Incidents" },
  // Its own section. The incident-page panel is for a question that occurs
  // while reading; this is for arriving with one. Sitting only inside an
  // incident, it was 1,500px down a 10,000px page and nobody found it.
  { href: "/ask", label: "Ask" },
  { href: "/observatory", label: "Observatory" },
  { href: "/infrastructure", label: "Infrastructure" },
  { href: "/actions", label: "Actions" },
  { href: "/audit", label: "Audit" },
];

/** Exact for the root, prefix elsewhere, so a detail page still shows its
 *  section as current. */
function isCurrent(href: string, pathname: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function Nav({ status }: { status?: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);

  // Navigating closes it. Without this the menu stays open over the page it
  // just moved to, and the first thing a visitor does on arriving somewhere is
  // dismiss the thing that took them there.
  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        toggle.current?.focus();
      }
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!panel.current?.contains(target) && !toggle.current?.contains(target)) {
        setOpen(false);
      }
    };

    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <>
      {/* The row. `lg` is where five labels, a search box and the status group
          stop colliding — measured, not guessed. */}
      <nav aria-label="Primary" className="hidden min-w-0 gap-1 text-sm lg:flex">
        {NAV.map((item) => (
          <NavLink key={item.href} {...item} current={isCurrent(item.href, pathname)} />
        ))}
      </nav>

      <button
        ref={toggle}
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        aria-controls="primary-menu"
        // `order-last` rather than a second `ml-auto`. Both the button and the
        // controls group claimed the gap, and the first one in source order won
        // — which left the menu button stranded in the middle of the header,
        // between the wordmark and the search icon.
        className="focusable order-last inline-flex h-9 w-9 shrink-0 items-center justify-center rounded border border-[rgb(var(--edge))] text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))] lg:hidden"
      >
        <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
        {/* Two bars rather than the usual three. The mark beside it is already
            an intricate piece of artwork, and a third line reads as noise next
            to it at this size. */}
        <span aria-hidden="true" className="flex flex-col gap-[5px]">
          <span
            className={`block h-px w-4 bg-current transition-transform ${
              open ? "translate-y-[3px] rotate-45" : ""
            }`}
          />
          <span
            className={`block h-px w-4 bg-current transition-transform ${
              open ? "-translate-y-[3px] -rotate-45" : ""
            }`}
          />
        </span>
      </button>

      {open && (
        <div
          ref={panel}
          id="primary-menu"
          className="rise absolute left-0 right-0 top-full z-50 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))] px-4 pb-4 pt-2 shadow-lg sm:px-6 lg:hidden"
        >
          <nav aria-label="Primary" className="flex flex-col">
            {NAV.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                current={isCurrent(item.href, pathname)}
                block
              />
            ))}
          </nav>
          {/* Execution mode belongs wherever the header is, not only where the
              header is wide. Someone reading on a phone has the same right to
              know whether an approval would change production. */}
          {status && (
            <div className="mt-3 border-t border-[rgb(var(--edge))] pt-3">{status}</div>
          )}
        </div>
      )}
    </>
  );
}

function NavLink({
  href,
  label,
  current,
  block = false,
}: {
  href: string;
  label: string;
  current: boolean;
  block?: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={`focusable shrink-0 rounded transition-colors ${
        block ? "px-3 py-2.5 text-sm" : "px-3 py-1.5"
      } ${
        current
          ? "bg-[rgb(var(--raised))] text-[rgb(var(--ink))]"
          : "text-[rgb(var(--muted))] hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
      }`}
    >
      {label}
    </Link>
  );
}
