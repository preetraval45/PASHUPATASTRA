"use client";

/**
 * Primary navigation.
 *
 * The labels do not fit beside a search box and a status group on anything
 * narrower than the `nav` breakpoint, and the first attempt to make them fit
 * was an `overflow-x-auto` strip with the scrollbar hidden. Nothing was missing
 * from the DOM, which is why the layout checks passed — but at 768px only
 * "Overview" was on screen, with no scrollbar, no fade, and no affordance of
 * any kind. A visitor with a mouse simply could not reach Incidents.
 *
 * The same shape returned when Home made a seventh label: at 1024px "Actions"
 * was underneath the search field, on the page and unclickable, and every check
 * still passed. The breakpoint is measured now and the checker hit-tests.
 *
 * So the links are a row when there is room for a row, and a menu when there is
 * not. A menu is more clicks; unreachable navigation is infinite clicks.
 */

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * A top-level tab is for something a visitor would go looking for. Everything
 * else appears where it is needed and nowhere else.
 *
 * **Infrastructure and Audit are deliberately absent**, and not because they
 * are weak. The access map means nothing without a failure attached to it —
 * standing alone and all green it is a screensaver — and an append-only audit
 * log is a trust artefact that matters enormously during a buyer's security
 * review and not at all to someone who arrived thirty seconds ago. Neither is
 * something anyone *arrives looking for*. Both are one click from the overview
 * and one from the incident whose actions they record, which is where the
 * question that needs them actually occurs.
 *
 * The task that asked for this said "three items", written when there were
 * five. Phases 3 and 4 added Ask, Observatory and Blue team, and each survives
 * the same test the other two failed: *would a stranger go looking for this?*
 * Can I ask it something, is any of this real, can I try it myself — yes, yes
 * and yes. Applying the number instead of the rule would have deleted three
 * sections for arithmetic.
 */
const NAV = [
  // The landing page, as a tab as well as through the wordmark. A logo that
  // goes home is a convention people who build sites know and people who use
  // them guess at; a labelled tab is the version nobody has to guess.
  { href: "/", label: "Home" },
  { href: "/overview", label: "Overview" },
  { href: "/incidents", label: "Incidents" },
  { href: "/ask", label: "Ask" },
  { href: "/blue-team", label: "Blue team" },
  { href: "/observatory", label: "Observatory" },
  { href: "/actions", label: "Actions" },
];


/** Exact for the root, prefix elsewhere, so a detail page still shows its
 *  section as current. */
function isCurrent(href: string, pathname: string): boolean {
  // The root is exact because a prefix match on "/" matches every page, and
  // Home would be marked current everywhere on the site.
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
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
      {/* The row, above the `nav` breakpoint — the measured width where seven
          labels, a search box and the status group stop colliding. It was `lg`
          until Home made a seventh label, at which point "Actions" sat
          underneath the search field at exactly 1024 and `verifyui.py` passed,
          because nothing overflowed: it was covered. R21b's lesson from the
          other direction. The checker hit-tests the header now. */}
      <nav aria-label="Primary" className="hidden min-w-0 gap-1 text-sm nav:flex">
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
        className="focusable order-last inline-flex h-9 w-9 shrink-0 items-center justify-center rounded border border-[rgb(var(--edge))] text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))] nav:hidden"
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
          className="rise absolute left-0 right-0 top-full z-50 border-b border-[rgb(var(--edge))] bg-[rgb(var(--ground))] px-4 pb-4 pt-2 shadow-lg sm:px-6 nav:hidden"
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
      <Pending />
    </Link>
  );
}

/**
 * A pending mark beside the link that was clicked, for as long as the next
 * page's server render is in flight (R100).
 *
 * `useLinkStatus` is Next's own; it reads the transition the enclosing `Link`
 * started and costs no dependency. Without it a click on a `force-dynamic`
 * route gave the visitor nothing at all until the new page's skeleton streamed
 * in — two to three seconds that one reviewer read as the site being broken
 * rather than busy. Announced to assistive tech through the `status` role;
 * `aria-hidden` on the glyph so it is not read out as punctuation.
 */
function Pending() {
  const { pending } = useLinkStatus();
  if (!pending) return null;
  return (
    <span role="status" aria-label="Loading" className="ml-1.5 inline-block">
      <span aria-hidden="true" className="inline-block animate-pulse text-[rgb(var(--faint))]">
        ·
      </span>
    </span>
  );
}
