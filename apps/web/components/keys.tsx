"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

/**
 * Whether a keystroke landed in something the user is typing into.
 *
 * One implementation, because every bare-letter shortcut on the site needs this
 * exact answer and a second copy of it is a second answer: the day one of them
 * forgets `isContentEditable`, `j` starts jumping the incident list while
 * somebody is composing a question to the assistant.
 *
 * Modifier chords are deliberately not covered here. `Ctrl-K` inside a text
 * field is not a keystroke a field wants — nothing native happens — so the
 * palette claims it everywhere, and only the single-letter shortcuts defer.
 */
export function isTypingIn(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    (target instanceof HTMLElement && target.isContentEditable)
  );
}

/** Whether a modal is on screen. Single-letter shortcuts stand down while one
 *  is open: `j` scrolling the page behind an open palette is the page ignoring
 *  a dialog it just told the user was modal. */
export function aDialogIsOpen(): boolean {
  return document.querySelector('[role="dialog"][aria-modal="true"]') !== null;
}

/** One row of the shortcut list.
 *
 *  `mouse` is not documentation — it is the requirement. A keyboard shortcut
 *  with no pointer equivalent is a feature only people who read the help can
 *  reach, so the field is mandatory and the sheet prints it. */
export type Shortcut = {
  keys: string[];
  does: string;
  mouse: string;
};

/** True everywhere, so they live here rather than being registered by whichever
 *  component happens to bind them. `/` is bound by the header search and
 *  `Ctrl-K` by the palette; both predate this list, and a help sheet that
 *  omitted them would be a list of the shortcuts added most recently. */
const GLOBAL: Shortcut[] = [
  {
    keys: ["ctrl", "k"],
    does: "Search everything — incidents, entities, actions, advisories",
    mouse: "the search field in the header",
  },
  {
    keys: ["/"],
    does: "Jump to the search field",
    mouse: "click the search field",
  },
  {
    keys: ["?"],
    does: "This list",
    mouse: "Keyboard shortcuts, in the footer",
  },
  { keys: ["esc"], does: "Close whatever is open", mouse: "click outside it" },
];

type Registry = {
  page: Shortcut[];
  register: (id: string, shortcuts: Shortcut[]) => void;
  release: (id: string) => void;
  open: () => void;
};

const Context = createContext<Registry | null>(null);

/**
 * Holds the shortcuts the current page adds to the global ones.
 *
 * The sheet lists what is actually bound *here*, which is why this is a
 * registry rather than a written list: `j`/`k` move between incidents on the
 * incident list and nowhere else, and telling a reader on the audit page that
 * `j` moves to the next incident is worse than telling them nothing.
 */
export function ShortcutsProvider({ children }: { children: ReactNode }) {
  const [pages, setPages] = useState<Record<string, Shortcut[]>>({});
  const opener = useRef<(() => void) | null>(null);

  const bind = useCallback((fn: () => void) => {
    opener.current = fn;
  }, []);

  const register = useCallback((id: string, shortcuts: Shortcut[]) => {
    setPages((was) => ({ ...was, [id]: shortcuts }));
  }, []);

  const release = useCallback((id: string) => {
    setPages((was) => {
      const next = { ...was };
      delete next[id];
      return next;
    });
  }, []);

  const value = useMemo<Registry>(
    () => ({
      page: Object.values(pages).flat(),
      register,
      release,
      open: () => opener.current?.(),
    }),
    [pages, register, release],
  );

  return (
    <Context.Provider value={value}>
      {children}
      <Sheet bind={bind} page={value.page} />
    </Context.Provider>
  );
}

/** Declare what this page binds, for as long as it is mounted. */
export function useShortcuts(shortcuts: Shortcut[]) {
  const registry = useContext(Context);
  const id = useId();
  // Serialised, so a caller passing a fresh array literal every render — which
  // is every caller — does not re-register on every render.
  const key = JSON.stringify(shortcuts);

  useEffect(() => {
    if (!registry) return;
    registry.register(id, JSON.parse(key) as Shortcut[]);
    return () => registry.release(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, key]);
}

/** The footer affordance. `?` is invisible until somebody presses it, and a
 *  shortcut list nobody can find is the same as no shortcut list. */
export function ShortcutsButton({ className = "" }: { className?: string }) {
  const registry = useContext(Context);
  return (
    <button
      type="button"
      onClick={() => registry?.open()}
      className={`focusable rounded hover:text-[rgb(var(--muted))] ${className}`}
    >
      Keyboard shortcuts <kbd className="rounded border border-[rgb(var(--edge))] px-1">?</kbd>
    </button>
  );
}

function Sheet({ bind, page }: { bind: (fn: () => void) => void; page: Shortcut[] }) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);
  const closer = useRef<HTMLButtonElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);

  const show = useCallback(() => {
    restoreTo.current = document.activeElement as HTMLElement | null;
    setOpen(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    // Back to whatever had focus, for the reason the palette does it: focus
    // dropped on <body> means the next Tab starts from the top of the document.
    restoreTo.current?.focus?.();
  }, []);

  // Braces, not a concise arrow. `bind` returns the function it stored, and an
  // effect that returns a function has handed React a cleanup — so the first
  // time the registry changed, React "cleaned up" by calling `show`, and the
  // shortcut sheet opened itself on page load.
  useEffect(() => {
    bind(show);
  }, [bind, show]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "?" || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTypingIn(event.target)) return;
      if (!open && aDialogIsOpen()) return;
      event.preventDefault();
      if (open) close();
      else show();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, show]);

  useEffect(() => {
    if (open) closer.current?.focus();
  }, [open]);

  if (!open) return null;

  const rows = [...GLOBAL, ...page];

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[12vh] backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        className="panel w-full max-w-xl overflow-hidden shadow-2xl"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            close();
          } else if (event.key === "Tab") {
            event.preventDefault();
            closer.current?.focus();
          }
        }}
      >
        <div className="flex items-center gap-3 border-b border-[rgb(var(--edge))] px-4 py-3">
          <h2 className="label">Keyboard shortcuts</h2>
          <button
            ref={closer}
            type="button"
            onClick={close}
            className="focusable ml-auto rounded px-1 text-sm text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
          >
            close
          </button>
        </div>

        <ul className="max-h-[60vh] divide-y divide-[rgb(var(--edge))] overflow-y-auto">
          {rows.map((row) => (
            <li key={row.keys.join("+") + row.does} className="px-4 py-3 text-sm">
              <div className="flex items-baseline gap-3">
                <span className="flex shrink-0 items-baseline gap-1">
                  {row.keys.map((key) => (
                    <kbd
                      key={key}
                      className="mono rounded border border-[rgb(var(--edge-strong))] px-1.5 py-0.5 text-xs"
                    >
                      {key}
                    </kbd>
                  ))}
                </span>
                <span className="min-w-0 flex-1">{row.does}</span>
              </div>
              {/* Every shortcut, with the thing to click instead. Nothing here
                  is keyboard-only: a shortcut is an accelerant, and a page that
                  can only be operated by someone who has read this sheet has
                  used the sheet to excuse an interface. */}
              <div className="mt-1 pl-1 text-xs text-[rgb(var(--faint))]">or {row.mouse}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
