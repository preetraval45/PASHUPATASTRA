"use client";

import Link from "next/link";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * Header search.
 *
 * Submits to `/search` rather than filtering in place. Results come from the
 * API on the server, so what is searched is the whole topology and incident
 * list — not whichever page happens to be loaded, which is the version of
 * search that quietly misses things.
 *
 * `/` focuses it. During an incident the operator already knows the name of the
 * thing they are looking for; making them reach for the mouse to type it is the
 * slowest part of the interaction.
 */
export function Search() {
  const router = useRouter();
  const params = useSearchParams();
  const input = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(params.get("q") ?? "");

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable;
      if (event.key === "/" && !typing) {
        event.preventDefault();
        input.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      {/* Below `sm` there is no room for a field beside a logo, a mode
          indicator and a menu button. A link to the search page rather than a
          field that expands over the header: the page it leads to is the same
          one submitting the field leads to, so nothing is lost but a keystroke,
          and nothing covers the page underneath. */}
      <Link
        href="/search"
        aria-label="Search entities and incidents"
        className="focusable inline-flex h-9 w-9 shrink-0 items-center justify-center rounded border border-[rgb(var(--edge))] text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))] sm:hidden"
      >
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" />
          <path d="M10.5 10.5 L14 14" stroke="currentColor" strokeLinecap="round" />
        </svg>
      </Link>

    <form
      role="search"
      className="relative hidden min-w-0 sm:block sm:w-44 md:w-52 lg:w-56 xl:w-64"
      onSubmit={(event) => {
        event.preventDefault();
        const query = value.trim();
        if (query) router.push(`/search?q=${encodeURIComponent(query)}`);
      }}
    >
      <label htmlFor="site-search" className="sr-only">
        Search entities and incidents
      </label>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[rgb(var(--faint))]"
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="7" cy="7" r="4.5" />
          <path d="M10.5 10.5 14 14" strokeLinecap="round" />
        </svg>
      </span>
      <input
        id="site-search"
        ref={input}
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search entities, incidents"
        title="Press / to focus this field, or Ctrl-K (Cmd-K) for the command palette"
        autoComplete="off"
        className="focusable w-full rounded border border-[rgb(var(--edge))] bg-[rgb(var(--raised))] py-1.5 pl-8 pr-8 text-sm text-[rgb(var(--ink))] placeholder:text-[rgb(var(--faint))] [&::-webkit-search-cancel-button]:appearance-none"
      />
      <kbd
        aria-hidden="true"
        className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-[rgb(var(--edge))] px-1.5 text-[10px] text-[rgb(var(--faint))] sm:block"
      >
        /
      </kbd>
    </form>
    </>
  );
}
