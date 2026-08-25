"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { SearchItem } from "@/lib/api";

/**
 * The command palette. `Cmd-K` on a Mac, `Ctrl-K` everywhere else.
 *
 * **It never waits on a request.** The index is fetched once on the server and
 * handed down as a prop, so every keystroke filters an array already in memory.
 * A palette that round-trips per keystroke is slower than the navigation it
 * replaces, which would make it a worse version of the thing it is supposed to
 * beat — and the same is true of one that fetches four endpoints when it opens.
 *
 * **It is not the only way in.** A keyboard shortcut is invisible on a phone
 * and unavailable to anyone who does not know it, so the header keeps its
 * search field and its search link, and this is an accelerant rather than a
 * replacement. R60 asks for exactly that: degrade to a visible affordance, not
 * to a shortcut nobody can type.
 *
 * Focus is captured on open and **returned to whatever had it** on close.
 * Losing focus to `<body>` after closing a dialog means a keyboard user's next
 * Tab starts from the top of the document, which is how a shortcut that was
 * meant to save time costs it.
 */

/** The four the task names, plus the two most-asked-for pages.
 *
 *  These exist because a stranger does not know what to type. "Show me a real
 *  incident" is the question; `INC-2026-0903` is an answer they have no way to
 *  guess, and a palette that only matches ids is a palette for people who
 *  already know their way around. */
const JUMPS: SearchItem[] = [
  {
    kind: "jump",
    label: "Show me a worked incident",
    hint: "the whole chain, evidence through to a scored plan",
    href: "/incidents",
  },
  {
    kind: "jump",
    label: "Let me work one myself",
    hint: "blue team mode",
    href: "/blue-team",
  },
  {
    kind: "jump",
    label: "Show today's real attacks",
    hint: "ransomware claims, live C2, disclosed breaches",
    href: "/observatory",
  },
  {
    kind: "jump",
    label: "Talk to the assistant",
    hint: "grounded in what was actually retrieved",
    href: "/ask",
  },
];

const PAGES: SearchItem[] = [
  { kind: "page", label: "Home", hint: "what this is", href: "/" },
  { kind: "page", label: "Overview", hint: "the console", href: "/overview" },
  { kind: "page", label: "Incidents", hint: "all of them", href: "/incidents" },
  { kind: "page", label: "Observatory", hint: "real attacks, polled hourly", href: "/observatory" },
  { kind: "page", label: "Actions", hint: "the registry and its risk scores", href: "/actions" },
  { kind: "page", label: "Audit", hint: "append-only ledger", href: "/audit" },
  { kind: "page", label: "How it works", hint: "tiers, gates, the loop", href: "/how-it-works" },
  { kind: "page", label: "Ask", hint: "the assistant", href: "/ask" },
  { kind: "page", label: "Blue team", hint: "work one yourself", href: "/blue-team" },
];

const KIND_LABEL: Record<string, string> = {
  jump: "go",
  page: "page",
  incident: "incident",
  entity: "entity",
  action: "action",
  advisory: "advisory",
};

/**
 * Subsequence match, scored.
 *
 * Not a library. The whole matcher is twenty lines and a dependency here would
 * be shipped to every visitor on every page to rank at most a few hundred short
 * strings.
 *
 * Returns `null` for no match so the caller can filter on it, and a lower score
 * for a worse match — consecutive characters and matches at a word boundary
 * score better, which is what makes `ws48` find `ws-0148` and rank it above a
 * string that merely contains those letters scattered through it.
 */
function score(needle: string, haystack: string): number | null {
  if (!needle) return 0;
  const text = haystack.toLowerCase();
  let at = 0;
  let total = 0;
  let streak = 0;

  for (const char of needle) {
    const found = text.indexOf(char, at);
    if (found === -1) return null;
    if (found === at && at > 0) {
      streak += 1;
      total += 4 + streak;
    } else {
      streak = 0;
      total += 1;
      const before = text[found - 1];
      // A word boundary — `ws-0148` matched at the `0` after the dash.
      if (found === 0 || before === " " || before === "-" || before === ":" || before === "/") {
        total += 3;
      }
    }
    at = found + 1;
  }
  // Shorter haystacks win ties: an exact-ish match on a short label beats the
  // same letters buried in a long advisory title.
  return total - haystack.length * 0.02;
}

export function CommandPalette({ index }: { index: SearchItem[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);

  const input = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);
  const listbox = useRef<HTMLUListElement>(null);

  const everything = useMemo(() => [...JUMPS, ...PAGES, ...index], [index]);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      // Nothing typed: the named jumps, which are the answer to "I do not know
      // what to type".
      return [...JUMPS, ...PAGES].slice(0, 10);
    }
    return everything
      .map((item) => {
        const best = Math.max(
          score(needle, item.label) ?? -Infinity,
          (score(needle, item.hint ?? "") ?? -Infinity) - 4,
        );
        return { item, best };
      })
      .filter((row) => row.best > -Infinity)
      .sort((a, b) => b.best - a.best)
      .slice(0, 12)
      .map((row) => row.item);
  }, [query, everything]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setCursor(0);
    // Back to whatever had focus. Without this the next Tab starts from the top
    // of the document.
    restoreTo.current?.focus?.();
  }, []);

  const go = useCallback(
    (item: SearchItem | undefined) => {
      if (!item) return;
      close();
      router.push(item.href);
    },
    [close, router],
  );

  // Open. Bound on the window so it works from any page, and deliberately not
  // stood down while a field has focus: `Ctrl-K` does nothing native in a text
  // box, so claiming it there costs nobody a keystroke. The single-letter
  // shortcuts are the ones that have to defer — see `isTypingIn`.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        restoreTo.current = document.activeElement as HTMLElement | null;
        setOpen((was) => !was);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  // Keep the highlighted row in view when arrowing past the fold.
  useEffect(() => {
    const node = listbox.current?.children[cursor] as HTMLElement | undefined;
    node?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  useEffect(() => setCursor(0), [query]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[12vh] backdrop-blur-sm"
      // A click on the backdrop closes. `onMouseDown` rather than `onClick`, so
      // a drag that starts inside the panel and ends outside it does not close
      // the thing the drag was selecting text in.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="panel w-full max-w-xl overflow-hidden shadow-2xl"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            close();
          } else if (event.key === "ArrowDown") {
            event.preventDefault();
            setCursor((at) => (results.length ? (at + 1) % results.length : 0));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setCursor((at) =>
              results.length ? (at - 1 + results.length) % results.length : 0,
            );
          } else if (event.key === "Enter") {
            event.preventDefault();
            go(results[cursor]);
          } else if (event.key === "Tab") {
            // The trap. There is exactly one focusable element in here, so Tab
            // has nowhere legitimate to go and letting it out would put focus
            // on the page behind an open dialog.
            event.preventDefault();
            input.current?.focus();
          }
        }}
      >
        <div className="border-b border-[rgb(var(--edge))] px-4 py-3">
          <label htmlFor="palette-input" className="sr-only">
            Search incidents, entities, advisories and actions
          </label>
          <input
            id="palette-input"
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search, or pick somewhere to go"
            autoComplete="off"
            spellCheck={false}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-results"
            aria-activedescendant={results[cursor] ? `palette-row-${cursor}` : undefined}
            className="w-full bg-transparent text-base text-[rgb(var(--ink))] outline-none placeholder:text-[rgb(var(--faint))]"
          />
        </div>

        <ul
          id="palette-results"
          ref={listbox}
          role="listbox"
          aria-label="Results"
          className="max-h-[52vh] overflow-y-auto py-1"
        >
          {results.length === 0 && (
            <li className="px-4 py-6 text-sm text-[rgb(var(--faint))]">
              Nothing matches {query.trim()}.
            </li>
          )}
          {results.map((item, at) => (
            <li
              key={`${item.kind}:${item.href}:${item.label}`}
              id={`palette-row-${at}`}
              role="option"
              aria-selected={at === cursor}
              onMouseEnter={() => setCursor(at)}
              onMouseDown={(event) => {
                event.preventDefault();
                go(item);
              }}
              className={`flex cursor-pointer items-baseline gap-3 px-4 py-2 text-sm ${
                at === cursor ? "bg-[rgb(var(--raised))]" : ""
              }`}
            >
              <span className="label w-16 shrink-0 text-[rgb(var(--faint))]">
                {KIND_LABEL[item.kind] ?? item.kind}
              </span>
              <span className="min-w-0 flex-1 break-words">
                <span className="text-[rgb(var(--ink))]">{item.label}</span>
                {item.hint && (
                  <span className="ml-2 text-xs text-[rgb(var(--muted))]">{item.hint}</span>
                )}
              </span>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[rgb(var(--edge))] px-4 py-2 text-[11px] text-[rgb(var(--faint))]">
          <span>
            <kbd className="rounded border border-[rgb(var(--edge))] px-1">↑</kbd>{" "}
            <kbd className="rounded border border-[rgb(var(--edge))] px-1">↓</kbd> move
          </span>
          <span>
            <kbd className="rounded border border-[rgb(var(--edge))] px-1">enter</kbd> open
          </span>
          <span>
            <kbd className="rounded border border-[rgb(var(--edge))] px-1">esc</kbd> close
          </span>
          <span className="ml-auto">{results.length} shown</span>
        </div>
      </div>
    </div>
  );
}
