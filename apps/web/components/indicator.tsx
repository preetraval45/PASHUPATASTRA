"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { lookupIndicator, type IndicatorReport } from "@/lib/api";
import { defang, refang } from "@/lib/defang";
import { split, type IndicatorKind } from "@/lib/indicators";

/**
 * Indicators, in place (R78).
 *
 * Any address, hash, domain or CVE the console renders becomes a button that
 * asks what is already known about it. Three properties, each of which is a
 * clause of the task rather than a nicety:
 *
 * **Nothing blocks the page.** The markup is computed at render — `split` is
 * pure — and the lookup happens on click, in a popover, after the page is
 * already there. A reader who clicks nothing pays nothing, and a reader who
 * clicks waits for a popover rather than for a page.
 *
 * **A miss reads as nothing known.** `known: false` is an answer and is drawn
 * as one. The failure state is a different sentence again: "could not ask" is
 * not "nothing known", and a reader deciding whether an address is hostile
 * must not be shown the first when the second is true.
 *
 * **Looked up once.** The module-level cache survives re-renders and
 * navigation within the session, so the same address clicked on three pages
 * is one request; the API caches too, for everyone else.
 *
 * The popover is a real `<button>` with `aria-expanded` and a labelled region,
 * closes on Escape and on an outside click, and returns focus — the shortcut
 * sheet's rules (R66), applied to the smallest surface on the site.
 */

type State =
  | { status: "idle" }
  | { status: "asking" }
  | { status: "answered"; report: IndicatorReport }
  | { status: "failed"; reason: string };

const CACHE = new Map<string, IndicatorReport>();

const KIND_LABEL: Record<IndicatorKind, string> = {
  ipv4: "address",
  domain: "domain",
  md5: "MD5",
  sha1: "SHA-1",
  sha256: "SHA-256",
  cve: "vulnerability",
};

/** Text with its indicators marked up.
 *
 *  Accepts text that is already defanged (the Observatory's, R115) or not
 *  (an incident's), and renders both the same way: defanged. The scan runs
 *  over the re-fanged form so a bracketed address is still recognised, and
 *  only the display and the props carry the bracketed one — the live value is
 *  rebuilt inside `Indicator` at the moment a reader asks about it. */
export function Indicators({ text }: { text: string }) {
  const pieces = split(refang(text));
  if (pieces.every((piece) => !("value" in piece))) return <>{defang(text)}</>;
  return (
    <>
      {pieces.map((piece, index) =>
        "value" in piece ? (
          <Indicator key={`${piece.start}-${index}`} value={defang(piece.value)} kind={piece.kind} />
        ) : (
          <span key={`t-${index}`}>{defang(piece.text)}</span>
        ),
      )}
    </>
  );
}

export function Indicator({ value, kind }: { value: string; kind: IndicatorKind }) {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [state, setState] = useState<State>({ status: "idle" });
  const wrapper = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  // Upgraded to a button after paint, and only outside a link.
  //
  // Two things at once, and both are the same shape as R61's highlight: the
  // server renders the plain value, and the interactivity arrives afterwards.
  // That keeps the markup identical to what it was — no hydration mismatch, and
  // a reader with no JavaScript sees the text unchanged — and it is the only
  // point at which the surrounding markup can be consulted.
  //
  // **An indicator inside a link stays text.** A `<button>` inside an `<a>` is
  // interactive content nested in interactive content: the parser keeps it,
  // the link takes the click, and the popover never opens — which is exactly
  // what the deployed-site check found on the causal chain, where every
  // evidence ref is a link. The link has a destination and the reader expects
  // to go there; the same address is clickable wherever it is not a link.
  useEffect(() => {
    setEnabled(wrapper.current?.closest("a") === null);
  }, []);

  const ask = useCallback(async () => {
    // The only place the live form exists, and only in the browser (R115).
    const live = refang(value);
    const cached = CACHE.get(live);
    if (cached) {
      setState({ status: "answered", report: cached });
      return;
    }
    setState({ status: "asking" });
    const result = await lookupIndicator(live);
    if (result.ok) {
      CACHE.set(live, result.report);
      setState({ status: "answered", report: result.report });
    } else {
      // Deliberately not "nothing known". The catalogues having nothing and
      // our not having been able to ask are different facts, and only one of
      // them is a reason to relax about an address.
      setState({ status: "failed", reason: result.reason });
    }
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    const onClick = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  if (!enabled) {
    return (
      <span ref={wrapper} data-indicator-text={value}>
        {value}
      </span>
    );
  }

  return (
    <span ref={wrapper} className="relative inline-block">
      <button
        ref={button}
        type="button"
        data-indicator={value}
        data-kind={kind}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        title={`What is known about this ${KIND_LABEL[kind]}`}
        onClick={() => {
          const next = !open;
          setOpen(next);
          if (next && state.status === "idle") void ask();
        }}
        className="focusable mono rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
      >
        {value}
      </button>
      {open && (
        <span
          id={panelId}
          role="region"
          aria-label={`What is known about ${value}`}
          className="panel absolute left-0 top-full z-20 mt-1 block w-[min(22rem,80vw)] p-3 text-left text-xs shadow-lg"
        >
          <Answer state={state} value={value} kind={kind} />
        </span>
      )}
    </span>
  );
}

function Answer({ state, value, kind }: { state: State; value: string; kind: IndicatorKind }) {
  if (state.status === "asking") {
    return <span className="text-[rgb(var(--faint))]">looking in what is already stored…</span>;
  }
  if (state.status === "failed") {
    return (
      <span className="text-[rgb(var(--warn))]">
        Could not ask — {state.reason}. This is not the same as nothing being known.
      </span>
    );
  }
  if (state.status !== "answered") return null;

  const { report } = state;
  if (!report.known) {
    return (
      <span className="block space-y-1.5">
        <span className="block">
          <span className="mono">{value}</span> — nothing known.
        </span>
        <span className="block text-[rgb(var(--faint))]">
          No entry for this {KIND_LABEL[kind]} in {report.consulted}. Nothing was asked of
          anyone else.
        </span>
      </span>
    );
  }

  return (
    <span className="block space-y-2">
      <span className="block">
        <span className="mono">{value}</span> — {report.report_count} report
        {report.report_count === 1 ? "" : "s"} from {report.sources.join(", ")}.
      </span>
      <span className="block space-y-1">
        {report.reports.slice(0, 4).map((entry) => (
          <span key={entry.event_id} className="block">
            <span className="text-[rgb(var(--faint))]">{(entry.occurred_at ?? "").slice(0, 10)}</span>{" "}
            {entry.title || entry.source}
            {entry.url && (
              <>
                {" "}
                <a
                  href={entry.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="focusable rounded underline decoration-dotted"
                >
                  advisory
                </a>
              </>
            )}
          </span>
        ))}
      </span>
      <span className="block text-[rgb(var(--faint))]">
        From {report.consulted}. {report.note}
      </span>
    </span>
  );
}
