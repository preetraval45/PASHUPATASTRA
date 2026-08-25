"use client";

/**
 * Sati, on the incident page.
 *
 * The panel exists to make one property visible from outside the code: every
 * sentence is traceable to something stored. So the citations are links, the
 * dropped ones are shown rather than hidden, and an answer the API marked
 * ungrounded says so on its face. A chat that renders prose and nothing else
 * would look identical whether or not any of that were true.
 *
 * Collapsed by default. An assistant that opens itself on arrival is a thing to
 * dismiss before reading the incident, and the incident is why anyone is here.
 */

import Link from "next/link";
import { hrefFor } from "@/lib/refs";
import { useCallback, useEffect, useRef, useState } from "react";

import { askAgent, tierLabel, type ChatAnswer, type Incident } from "@/lib/api";
import { Badge, Ident } from "@/components/ui";

/**
 * Four openings, in the order an analyst actually asks them: what happened,
 * how do we know, how bad is it, what now. They are also the reason the answer
 * cache earns its keep — everyone clicks the same four, so almost every visitor
 * after the first is served without spending a token.
 */
export const STARTERS = [
  "What happened?",
  "How do we know — what is the evidence?",
  "What is the blast radius?",
  "What should we do first?",
] as const;

export type Turn =
  | { role: "you"; text: string }
  | { role: "sati"; answer: ChatAnswer }
  | { role: "error"; text: string; retryable: boolean };

export function ChatPanel({ incident }: { incident: Incident }) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  // Follow the conversation as it grows, but only the log — scrolling the page
  // would yank an incident out from under someone who is reading it.
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy) return;

      setTurns((prior) => [...prior, { role: "you", text }]);
      setDraft("");
      setBusy(true);

      const result = await askAgent(incident.id, text);
      setTurns((prior) => [
        ...prior,
        "answer" in result
          ? { role: "sati", answer: result.answer }
          : { role: "error", text: result.error, retryable: result.retryable },
      ]);
      setBusy(false);
    },
    [busy, incident.id],
  );

  if (!open) {
    return (
      <div className="mt-6">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="focusable flex w-full items-center gap-3 rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-4 py-3 text-left transition hover:bg-[rgb(var(--raised))]"
        >
          <span aria-hidden="true" className="text-[rgb(var(--astra))]">
            ◈
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium">Ask about this incident</span>
            <span className="block text-xs text-[rgb(var(--faint))]">
              Answers cite stored evidence, and cannot act on anything
            </span>
          </span>
          <span aria-hidden="true" className="text-[rgb(var(--faint))]">
            +
          </span>
        </button>
      </div>
    );
  }

  return (
    <section
      aria-label="Ask about this incident"
      className="mt-6 overflow-hidden rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))]"
    >
      <header className="flex items-center gap-3 border-b border-[rgb(var(--edge))] px-4 py-3">
        <span aria-hidden="true" className="text-[rgb(var(--astra))]">
          ◈
        </span>
        <h2 className="min-w-0 flex-1 text-sm font-medium">
          Ask about {incident.id}
        </h2>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="focusable rounded px-2 py-1 text-xs text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]"
        >
          Close
        </button>
      </header>

      <div
        ref={log}
        aria-live="polite"
        className="max-h-[28rem] space-y-4 overflow-y-auto px-4 py-4"
      >
        {turns.length === 0 && (
          <p className="text-sm text-[rgb(var(--faint))]">
            Sati reads this incident&rsquo;s evidence and answers from it. It can
            name an action, but it cannot run one &mdash; anything it proposes
            goes to a human for approval.
          </p>
        )}

        {turns.map((turn, index) => (
          <TurnView key={index} turn={turn} incident={incident} />
        ))}

        {busy && (
          <p className="flex items-center gap-3 text-sm text-[rgb(var(--faint))]">
            {/* The animation is decorative and hidden from assistive tech; the
                sentence beside it is what actually reports the state, and
                `aria-live` on the log announces it. */}
            <span className="loose" aria-hidden="true" />
            Reading the evidence…
          </p>
        )}
      </div>

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2 border-t border-[rgb(var(--edge))] px-4 py-3">
          {STARTERS.map((starter) => (
            <button
              key={starter}
              type="button"
              disabled={busy}
              onClick={() => ask(starter)}
              className="focusable rounded-full border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-xs transition hover:bg-[rgb(var(--raised))] disabled:opacity-50"
            >
              {starter}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(draft);
        }}
        className="flex items-end gap-2 border-t border-[rgb(var(--edge))] px-4 py-3"
      >
        <label htmlFor="sati-question" className="sr-only">
          Your question about {incident.id}
        </label>
        <textarea
          id="sati-question"
          ref={input}
          rows={1}
          value={draft}
          disabled={busy}
          onChange={(event) => setDraft(event.target.value)}
          // Enter sends, Shift+Enter breaks the line. The reverse traps anyone
          // who types the way every other chat box has taught them to.
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              ask(draft);
            }
          }}
          placeholder="Ask about this incident…"
          className="focusable min-h-[2.5rem] flex-1 resize-none rounded border border-[rgb(var(--edge-strong))] bg-[rgb(var(--bg))] px-3 py-2 text-sm placeholder:text-[rgb(var(--faint))]"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="focusable rounded border border-[rgb(var(--edge-strong))] px-3 py-2 text-sm transition hover:bg-[rgb(var(--raised))] disabled:opacity-40"
        >
          Ask
        </button>
      </form>
    </section>
  );
}

export function TurnView({ turn, incident }: { turn: Turn; incident: Incident }) {
  if (turn.role === "you") {
    return (
      <p
        data-turn="you"
        className="ml-auto max-w-[85%] rounded-lg rounded-br-sm bg-[rgb(var(--raised))] px-3 py-2 text-sm"
      >
        {turn.text}
      </p>
    );
  }

  if (turn.role === "error") {
    return (
      <p
        data-turn="error"
        className="rounded-lg border border-[rgb(var(--edge))] px-3 py-2 text-sm text-[rgb(var(--faint))]"
      >
        {turn.text}
        {turn.retryable && " You can ask again in a moment."}
      </p>
    );
  }

  const { answer } = turn;
  return (
    // The data attributes are how `scripts/verifychat.py` finds an answer.
    // It used to locate turns by position and read the visitor's own question
    // back as though it were the reply — a check that passed while testing
    // nothing.
    <div data-turn="sati" className="max-w-[95%] space-y-2">
      <p data-answer className="whitespace-pre-wrap text-sm leading-relaxed">
        {answer.answer}
      </p>

      {answer.evidence_refs.length > 0 && (
        <p data-evidence className="mono text-[11px] text-[rgb(var(--faint))]">
          evidence:{" "}
          {answer.evidence_refs.map((ref, index) => (
            <span key={ref}>
              {index > 0 && ", "}
              <Link
                href={hrefFor(ref, incident.id)}
                className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
              >
                {label(ref, incident.id)}
              </Link>
            </span>
          ))}
        </p>
      )}

      {answer.considered?.length > 0 && <RuledOutList answer={answer} incident={incident} />}

      {answer.trace?.length > 0 && <Steps answer={answer} incident={incident} />}

      {answer.proposed_action_id && answer.verdict && (
        <Proposal answer={answer} />
      )}

      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[rgb(var(--faint))]">
        {/* Not decoration. An answer nobody can trace is the failure mode this
            whole design is arranged against, so when it happens it is stated
            rather than left for the reader to infer from a missing line. */}
        {!answer.grounded && (
          <Badge status="warning">not grounded</Badge>
        )}
        {!answer.answerable && <Badge status="neutral">not in the evidence</Badge>}
        {answer.truncated && <Badge status="neutral">cut short</Badge>}
        <span>{answer.cached ? "from cache" : `${answer.tokens} tokens`}</span>
        <span className="mono">{answer.model}</span>
        {answer.dropped_refs.length > 0 && (
          <span title="Cited by the model, but matching nothing that was retrieved">
            {answer.dropped_refs.length} unresolved citation
            {answer.dropped_refs.length > 1 && "s"} dropped
          </span>
        )}
      </p>
    </div>
  );
}

/**
 * What else the evidence could have meant, and what closed it.
 *
 * Not decoration and not hedging. The site's claim is that diagnoses are
 * *challenged* by evidence, and an answer that states only its conclusion is
 * asking to be believed. Each rejection names refs, each ref is a link, and
 * anything the agent could not support was dropped before it reached here — so
 * what is on screen is a rejection a reader can go and check.
 *
 * Shown open rather than behind a disclosure. A conclusion is more persuasive
 * than the doubt beside it already; putting the doubt one click further away
 * decides which of the two a reader sees.
 */
function RuledOutList({ answer, incident }: { answer: ChatAnswer; incident: Incident }) {
  return (
    <div data-considered className="rounded border border-[rgb(var(--edge))] px-3 py-2">
      <p className="label">Also possible, and what rules it out</p>
      <ul className="mt-2 space-y-1.5 text-xs">
        {answer.considered.map((item) => (
          <li key={item.reading}>
            <span className="text-[rgb(var(--muted))]">{item.reading}</span>{" "}
            <span className="mono text-[rgb(var(--faint))]">
              ruled out by{" "}
              {item.ruled_out_by.map((ref, index) => (
                <span key={ref}>
                  {index > 0 && ", "}
                  <Link
                    href={hrefFor(ref, incident.id)}
                    className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                  >
                    {label(ref, incident.id)}
                  </Link>
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
      {answer.dropped_considered?.length > 0 && (
        // Said out loud. An alternative dismissed on evidence that does not
        // exist is a thing the reader should know the agent tried to do.
        <p className="mt-2 text-[11px] text-[rgb(var(--warn))]">
          {answer.dropped_considered.length} more dismissed on evidence that resolved to
          nothing, and dropped
        </p>
      )}
    </div>
  );
}

/** How each trace step reads, in words rather than field names. */
const STEP: Record<string, string> = {
  tool_call: "looked up",
  tool_result: "read",
  refusal: "reached for a tool it was not given",
  answer: "answered",
  format: "re-asked for the structured form",
  budget_exhausted: "ran out of budget",
};

/**
 * The steps, with the records each one read.
 *
 * Collapsed, unlike the rejections above: this is the mechanical account, and a
 * reader wants it when they are already suspicious. What it must never be is a
 * narration — every lookup names the ids that came back, so "read
 * `evt-pg-connections`" can be clicked and disagreed with. A step that only
 * said "read logs" would be the agent describing itself.
 */
function Steps({ answer, incident }: { answer: ChatAnswer; incident: Incident }) {
  const lookups = answer.trace.filter((step) => step.kind !== "answer").length;
  return (
    <details data-trace className="text-xs">
      <summary className="focusable inline-block cursor-pointer rounded text-[11px] text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]">
        {lookups > 0
          ? `how it got there — ${lookups} step${lookups === 1 ? "" : "s"}`
          : "how it got there"}
      </summary>
      <ol className="mt-2 space-y-1 border-l border-[rgb(var(--edge))] pl-3">
        {answer.trace.map((step, index) => (
          <li key={index} className="flex min-w-0 flex-wrap items-baseline gap-x-2">
            <span className="mono shrink-0 text-[rgb(var(--faint))]">{step.hop}</span>
            <span className="text-[rgb(var(--muted))]">{STEP[step.kind] ?? step.kind}</span>
            {step.name && <Ident>{step.name}</Ident>}
            {step.detail?.entity_key && (
              <span className="mono min-w-0 break-all text-[rgb(var(--faint))]">
                {step.detail.entity_key}
              </span>
            )}
            {step.detail?.refs?.length ? (
              <span className="mono min-w-0 break-all text-[rgb(var(--faint))]">
                {step.detail.refs.map((ref, at) => (
                  <span key={ref}>
                    {at > 0 && ", "}
                    <Link
                      href={hrefFor(ref, incident.id)}
                      className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                    >
                      {label(ref, incident.id)}
                    </Link>
                  </span>
                ))}
              </span>
            ) : step.kind === "tool_result" ? (
              // A lookup that found nothing is a step too, and saying so is
              // what stops the absence reading as an omission.
              <span className="text-[rgb(var(--faint))]">nothing</span>
            ) : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

/**
 * A proposed action, and what policy said about it.
 *
 * Shown in full rather than summarised, because "the assistant suggested
 * isolating a host" and "the assistant suggested it, policy scored it 67, and
 * it needs a senior operator" are different statements, and only the second one
 * tells a reader what happens next.
 */
export function Proposal({ answer }: { answer: ChatAnswer }) {
  const verdict = answer.verdict!;
  const steps = verdict.tier_reasons ?? [];
  const last = steps[steps.length - 1];
  const binding = last && last.rule !== "risk_band" ? last : null;
  return (
    <div className="rounded border border-[rgb(var(--edge-strong))] bg-[rgb(var(--raised))] px-3 py-2 text-xs">
      <p className="flex flex-wrap items-center gap-2">
        <span className="text-[rgb(var(--faint))]">proposed</span>
        <Ident>{answer.proposed_action_id}</Ident>
        <Badge status={verdict.tier === "denied" ? "high" : "warning"}>
          {tierLabel(verdict.tier)}
        </Badge>
        <span className="text-[rgb(var(--faint))]">risk {verdict.effective_risk}</span>
      </p>
      {/* When the tier is not the one the score alone would give, the score is
          the wrong explanation for it. The binding rule is the last step the
          engine recorded, so this shows that rather than paraphrasing. */}
      {binding && (
        <p className="mt-1 text-[rgb(var(--muted))]">{binding.detail}</p>
      )}
      <p className="mt-1 text-[rgb(var(--faint))]">
        Queued for a human. Nothing has run &mdash; the assistant has no way to
        execute anything.
      </p>
    </div>
  );
}

/** Shortened for reading. The full ref is the link target either way, and
 *  `INC-2026-0901#chain-2` repeated four times is a wall of the same prefix. */
function label(ref: string, incidentId: string): string {
  if (ref.startsWith("audit:")) return "audit record";
  if (ref.startsWith(`${incidentId}#`)) return ref.slice(incidentId.length + 1);
  return ref;
}
