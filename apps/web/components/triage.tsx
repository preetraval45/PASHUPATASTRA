"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { aDialogIsOpen, isTypingIn, useShortcuts } from "@/components/keys";

/**
 * `j`/`k` down and up a list of incidents, `Enter` to open the one you are on.
 *
 * The order comes from the page, as an explicit index per item, rather than
 * from the order items happen to register in. React does not promise mount
 * order matches document order, and a triage list that moves down the page in
 * the wrong order is worse than one with no shortcuts at all — it looks like it
 * worked.
 *
 * Selection is a position, not a focus ring borrowed from something else: the
 * item wrapper takes focus so `Enter` has an unambiguous target and a screen
 * reader lands where the eye did. Clicking a card sets the same position, which
 * is what makes `j`/`k` an accelerant rather than a second, hidden interface.
 */

type List = {
  cursor: number;
  select: (index: number) => void;
  claim: (index: number, node: HTMLElement | null, href: string) => void;
};

const Context = createContext<List | null>(null);

export function TriageList({ children, of = "incident" }: { children: ReactNode; of?: string }) {
  const router = useRouter();
  const [cursor, setCursor] = useState(-1);
  const items = useRef(new Map<number, { node: HTMLElement | null; href: string }>());

  useShortcuts([
    { keys: ["j"], does: `Next ${of}`, mouse: "click one to select it" },
    { keys: ["k"], does: `Previous ${of}`, mouse: "click one to select it" },
    { keys: ["enter"], does: `Open the selected ${of}`, mouse: "click its id" },
  ]);

  const claim = useCallback((index: number, node: HTMLElement | null, href: string) => {
    if (node === null) items.current.delete(index);
    else items.current.set(index, { node, href });
  }, []);

  const select = useCallback((index: number) => setCursor(index), []);

  const move = useCallback((by: number) => {
    setCursor((at) => {
      const last = Math.max(...items.current.keys());
      if (!items.current.size) return -1;
      // From nowhere, `j` starts at the top and `k` at the bottom, rather than
      // both starting at the top and `k` appearing to do nothing.
      const next = at < 0 ? (by > 0 ? 0 : last) : Math.min(Math.max(at + by, 0), last);
      const node = items.current.get(next)?.node;
      node?.focus({ preventScroll: true });
      node?.scrollIntoView({ block: "start" });
      return next;
    });
  }, []);

  // The handler below is bound once; reading `cursor` inside it would read the
  // value from the render that bound it, which is always -1.
  const cursorRef = useRef(cursor);
  cursorRef.current = cursor;

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTypingIn(event.target)) return;
      if (aDialogIsOpen()) return;

      if (event.key === "j") {
        event.preventDefault();
        move(1);
      } else if (event.key === "k") {
        event.preventDefault();
        move(-1);
      } else if (event.key === "Enter") {
        // A link or a button already has a meaning for Enter. Taking it would
        // make the shortcut break the page for anyone tabbing through it.
        const active = document.activeElement;
        if (active instanceof HTMLAnchorElement || active instanceof HTMLButtonElement) return;
        const href = cursorRef.current >= 0 ? items.current.get(cursorRef.current)?.href : null;
        if (!href) return;
        event.preventDefault();
        router.push(href);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, router]);

  return <Context.Provider value={{ cursor, select, claim }}>{children}</Context.Provider>;
}

export function TriageItem({
  index,
  href,
  children,
}: {
  index: number;
  href: string;
  children: ReactNode;
}) {
  const list = useContext(Context);
  const node = useRef<HTMLDivElement>(null);
  const here = list?.cursor === index;

  useEffect(() => {
    list?.claim(index, node.current, href);
    return () => list?.claim(index, null, href);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, href]);

  return (
    <div
      ref={node}
      // Focusable but not in the tab order: Tab still walks the links inside
      // each card, which is the order a keyboard user without these shortcuts
      // expects. This is only somewhere for `j` to put focus.
      tabIndex={-1}
      data-triage={index}
      aria-current={here ? "true" : undefined}
      onMouseDown={() => list?.select(index)}
      // `scroll-mt-20` clears the sticky header, which otherwise covers the top
      // of every card `j` scrolls to.
      className={`scroll-mt-20 rounded-lg outline-none ${
        here ? "ring-2 ring-[rgb(var(--astra))] ring-offset-4 ring-offset-[rgb(var(--ground))]" : ""
      }`}
    >
      {children}
    </div>
  );
}
