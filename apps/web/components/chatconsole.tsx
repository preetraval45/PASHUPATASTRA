"use client";

/**
 * The full-page conversation with Sati.
 *
 * The incident-page panel is a sidebar: narrow, collapsed, for a question that
 * occurs to you while reading. This is the room you go to when the question is
 * the reason you came. So it gets the things a panel cannot afford — a picker
 * for which incident is being discussed, the incident's own facts kept in view
 * beside the conversation, and enough width that a cited answer is readable.
 *
 * The turn rendering is imported rather than rewritten. Two copies would drift,
 * and the half that drifts is always the citation rendering — which is the part
 * carrying the guarantee.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { STARTERS, TurnView, type Turn } from "@/components/chat";
import { Badge, Stated, statusForSeverity } from "@/components/ui";
import { askAgent, type Incident } from "@/lib/api";

export function ChatConsole({ incidents }: { incidents: Incident[] }) {
  const router = useRouter();
  const params = useSearchParams();

  const wanted = params.get("incident");
  const incident =
    incidents.find((candidate) => candidate.id === wanted) ?? incidents[0];

  // Keyed by incident, so switching does not carry one incident's answers into
  // a conversation about another — where they would look like answers about it.
  const [threads, setThreads] = useState<Record<string, Turn[]>>({});
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const turns = incident ? (threads[incident.id] ?? []) : [];

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy || !incident) return;

      const id = incident.id;
      setThreads((prior) => ({
        ...prior,
        [id]: [...(prior[id] ?? []), { role: "you", text }],
      }));
      setDraft("");
      setBusy(true);

      const result = await askAgent(id, text);
      setThreads((prior) => ({
        ...prior,
        [id]: [
          ...(prior[id] ?? []),
          "answer" in result
            ? { role: "sati", answer: result.answer }
            : { role: "error", text: result.error, retryable: result.retryable },
        ],
      }));
      setBusy(false);
      input.current?.focus();
    },
    [busy, incident],
  );

  if (!incident) {
    return (
      <p className="text-sm text-[rgb(var(--faint))]">
        There are no incidents to ask about. Sati answers from stored evidence,
        so it has nothing to work from until one exists.
      </p>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <section className="flex min-h-[32rem] min-w-0 flex-col overflow-hidden rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))]">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-[rgb(var(--edge))] px-4 py-3">
          <label htmlFor="ask-incident" className="text-xs text-[rgb(var(--faint))]">
            about
          </label>
          <select
            id="ask-incident"
            value={incident.id}
            onChange={(event) =>
              router.replace(`/ask?incident=${encodeURIComponent(event.target.value)}`)
            }
            className="focusable mono min-w-0 rounded border border-[rgb(var(--edge-strong))] bg-[rgb(var(--bg))] px-2 py-1 text-sm"
          >
            {incidents.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.id} — {candidate.severity}
              </option>
            ))}
          </select>
          <Badge status={statusForSeverity(incident.severity)}>
            {incident.severity}
          </Badge>
          <Link
            href={`/incidents/${encodeURIComponent(incident.id)}`}
            className="focusable ml-auto rounded text-xs text-[rgb(var(--faint))] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
          >
            open the incident
          </Link>
        </header>

        <div
          ref={log}
          aria-live="polite"
          className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6"
        >
          {turns.length === 0 ? (
            <Opening incident={incident} />
          ) : (
            turns.map((turn, index) => (
              <TurnView key={index} turn={turn} incident={incident} />
            ))
          )}

          {busy && (
            <p className="flex items-center gap-3 text-sm text-[rgb(var(--faint))]">
              <span className="loose" aria-hidden="true" />
              Reading the evidence…
            </p>
          )}
        </div>

        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2 border-t border-[rgb(var(--edge))] px-4 py-3 sm:px-6">
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
          className="flex items-end gap-2 border-t border-[rgb(var(--edge))] px-4 py-3 sm:px-6"
        >
          <label htmlFor="ask-question" className="sr-only">
            Your question about {incident.id}
          </label>
          <textarea
            id="ask-question"
            ref={input}
            rows={1}
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                ask(draft);
              }
            }}
            placeholder={`Ask about ${incident.id}…`}
            className="focusable min-h-[2.75rem] flex-1 resize-none rounded border border-[rgb(var(--edge-strong))] bg-[rgb(var(--bg))] px-3 py-2.5 text-sm placeholder:text-[rgb(var(--faint))]"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="focusable rounded border border-[rgb(var(--edge-strong))] px-4 py-2.5 text-sm transition hover:bg-[rgb(var(--raised))] disabled:opacity-40"
          >
            Ask
          </button>
        </form>
      </section>

      <Context incident={incident} />
    </div>
  );
}

/**
 * The empty state, which is where a visitor decides whether to trust anything
 * that follows. So it says what the thing does and — more usefully — what it
 * cannot do, rather than inviting a question and letting them discover the
 * limits by hitting one.
 */
function Opening({ incident }: { incident: Incident }) {
  return (
    <div className="space-y-3 text-sm">
      <p className="text-[rgb(var(--muted))]">
        Sati reads {incident.id} — its causal chain, the telemetry behind it, and
        the plan — and answers from that. Every claim carries a citation you can
        follow.
      </p>
      <p className="text-[rgb(var(--faint))]">
        It cannot act. Ask it to isolate a host and it will name the action and
        send it to a human for approval, which is the same path a person&rsquo;s
        request takes.
      </p>
    </div>
  );
}

/** The incident's own facts, beside the conversation rather than inside it —
 *  so an answer can be read against what is known without scrolling away. */
function Context({ incident }: { incident: Incident }) {
  const top = incident.hypotheses[0];
  return (
    <aside className="space-y-4 self-start rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 text-sm">
      <div>
        <p className="label mb-1">Diagnosis</p>
        <p className="text-[rgb(var(--muted))]">
          {top ? top.statement : "No hypothesis recorded."}
        </p>
        {top && (
          <p className="mono mt-1 text-xs text-[rgb(var(--faint))]">
            <Stated value={top.confidence} />
          </p>
        )}
      </div>

      <div>
        <p className="label mb-1">Affected</p>
        <ul className="space-y-0.5">
          {incident.affected_entities.map((entity) => (
            <li key={`${entity.kind}:${entity.id}`}>
              <Link
                href={`/entity/${encodeURIComponent(`${entity.kind}:${entity.id}`)}`}
                className="focusable mono rounded text-xs underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
              >
                {entity.kind}:{entity.id}
              </Link>
            </li>
          ))}
          {incident.affected_entities.length === 0 && (
            <li className="text-xs text-[rgb(var(--faint))]">none recorded</li>
          )}
        </ul>
      </div>

      <div>
        <p className="label mb-1">Blast radius</p>
        <p className="text-[rgb(var(--muted))]">
          {incident.impact.blast_radius_entities} entities ·{" "}
          {incident.impact.estimated_users_affected} users
        </p>
      </div>
    </aside>
  );
}
