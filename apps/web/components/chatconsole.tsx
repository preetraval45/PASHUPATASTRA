"use client";

/**
 * The full-screen conversation with Sati (RP-49).
 *
 * It was a panel partway down a document page: a website's idea of a chat. This
 * is the app's idea — the conversation fills the window, the input is pinned to
 * the bottom, the incidents you can ask about sit in a rail on the left, and the
 * incident's own facts can be kept open on the right so an answer is read
 * against what is known.
 *
 * What did not change is the part carrying the guarantee: each turn is rendered
 * by `TurnView` from `chat.tsx`, so citations, dropped refs, the withheld notice
 * and the model that answered look exactly as they do on the incident page.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { STARTERS, TurnView, type Turn } from "@/components/chat";
import { Listbox } from "@/components/listbox";
import { Icon } from "@/components/sidebar";
import { Badge, Stated, statusForSeverity } from "@/components/ui";
import { askAgent, type Incident, type ModelChoice } from "@/lib/api";

/** What each starter is for, shown under it on the empty screen. The starter
 *  text itself is unchanged — it is part of the answer-cache key. */
const STARTER_HINTS = [
  "The causal chain, in order",
  "The evidence behind the diagnosis",
  "Who and what is affected",
  "A next step, routed through policy",
] as const;

const THREADS_KEY = "pashu.ask.threads.v1";
const MODEL_KEY = "pashu.ask.model";
const KEEP_TURNS = 40;

export function ChatConsole({
  incidents,
  models,
  allowance,
}: {
  incidents: Incident[];
  models: ModelChoice[];
  allowance?: ReactNode;
}) {
  const router = useRouter();
  const params = useSearchParams();

  const wanted = params.get("incident");
  const incident = incidents.find((candidate) => candidate.id === wanted) ?? incidents[0];

  // Keyed by incident, so one incident's answers never appear in a conversation
  // about another — where they would read as answers about it. Kept in this
  // browser only; nothing about a visitor's questions is stored server-side
  // beyond the audit record every turn already writes.
  const [threads, setThreads] = useState<Record<string, Turn[]>>({});
  const [model, setModel] = useState<string>(models.find((m) => m.default)?.id ?? "default");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [context, setContext] = useState(true);

  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const turns = incident ? (threads[incident.id] ?? []) : [];

  useEffect(() => {
    try {
      const stored = localStorage.getItem(THREADS_KEY);
      if (stored) setThreads(JSON.parse(stored));
      const chosen = localStorage.getItem(MODEL_KEY);
      if (chosen && models.some((m) => m.id === chosen)) setModel(chosen);
    } catch {
      // Blocked or corrupt storage: start empty rather than fail.
    }
  }, [models]);

  const persist = useCallback((next: Record<string, Turn[]>) => {
    try {
      const trimmed = Object.fromEntries(
        Object.entries(next).map(([id, list]) => [id, list.slice(-KEEP_TURNS)]),
      );
      localStorage.setItem(THREADS_KEY, JSON.stringify(trimmed));
    } catch {
      // Not remembered; the conversation still works.
    }
  }, []);

  const update = useCallback(
    (id: string, change: (prior: Turn[]) => Turn[]) =>
      setThreads((prior) => {
        const next = { ...prior, [id]: change(prior[id] ?? []) };
        persist(next);
        return next;
      }),
    [persist],
  );

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [turns.length, busy, incident?.id]);

  // The composer grows with what is typed, up to a third of the window.
  useLayoutEffect(() => {
    const box = input.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, window.innerHeight / 3)}px`;
  }, [draft]);

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy || !incident) return;
      const id = incident.id;
      update(id, (prior) => [...prior, { role: "you", text }]);
      setDraft("");
      setBusy(true);

      const result = await askAgent(id, text, model);
      update(id, (prior) => [
        ...prior,
        "answer" in result
          ? { role: "sati", answer: result.answer }
          : { role: "error", text: result.error, retryable: result.retryable },
      ]);
      setBusy(false);
      input.current?.focus();
    },
    [busy, incident, model, update],
  );

  const choose = (id: string) => router.replace(`/ask?incident=${encodeURIComponent(id)}`);

  const chooseModel = (id: string) => {
    setModel(id);
    try {
      localStorage.setItem(MODEL_KEY, id);
    } catch {
      // Not remembered across visits.
    }
  };

  if (!incident) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="max-w-md text-center text-sm text-[rgb(var(--faint))]">
          There are no incidents to ask about. Sati, the investigation agent, answers from stored
          evidence, so it has nothing to work from until one exists.
        </p>
      </div>
    );
  }

  const current = models.find((m) => m.id === model) ?? models[0];
  const top = incident.hypotheses[0];

  return (
    <div className="flex min-h-0 flex-1">
      {/* Incidents, as a rail rather than a dropdown. Which one is being
          discussed is the first fact about any answer, so it stays in view. */}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-[rgb(var(--edge))] bg-[rgb(var(--panel))]/60 lg:flex">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-[rgb(var(--edge))] px-4">
          <p className="label">Incidents</p>
          <span className="tnum text-xs text-[rgb(var(--faint))]">{incidents.length}</span>
        </div>
        <ul className="flex-1 space-y-1 overflow-y-auto p-2">
          {incidents.map((candidate) => {
            const active = candidate.id === incident.id;
            const asked = (threads[candidate.id] ?? []).filter((t) => t.role === "you").length;
            return (
              <li key={candidate.id}>
                <button
                  type="button"
                  onClick={() => choose(candidate.id)}
                  aria-current={active ? "true" : undefined}
                  className={`focusable w-full rounded-lg border px-3 py-2.5 text-left transition ${
                    active
                      ? "border-[rgb(var(--astra))]/50 bg-[rgb(var(--raised))]"
                      : "border-transparent hover:bg-[rgb(var(--raised))]"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="mono text-xs text-[rgb(var(--ink))]">{candidate.id}</span>
                    <span className="ml-auto">
                      <Badge status={statusForSeverity(candidate.severity)}>{candidate.severity}</Badge>
                    </span>
                  </span>
                  <span className="mt-1 line-clamp-2 block text-xs leading-snug text-[rgb(var(--muted))]">
                    {candidate.hypotheses[0]?.statement ?? "No diagnosis yet"}
                  </span>
                  {asked > 0 && (
                    <span className="tnum mt-1.5 block text-[11px] text-[rgb(var(--faint))]">
                      {asked} question{asked === 1 ? "" : "s"} asked
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
        {allowance && <div className="shrink-0 border-t border-[rgb(var(--edge))] px-4 py-3">{allowance}</div>}
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-[rgb(var(--edge))] px-3 sm:gap-3 sm:px-4">
          <div className="min-w-0 lg:hidden">
            <Listbox
              label="Incident"
              value={incident.id}
              onChange={choose}
              dataAttr="data-ask-incident"
              buttonClassName="mono text-xs"
              options={incidents.map((candidate) => ({
                value: candidate.id,
                label: (
                  <span className="mono">
                    {candidate.id} · {candidate.severity}
                  </span>
                ),
                hint: candidate.hypotheses[0]?.statement,
              }))}
            />
          </div>
          <div className="hidden min-w-0 items-center gap-2 lg:flex">
            <span className="mono text-sm">{incident.id}</span>
            <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
            {top && (
              <span className="hidden min-w-0 truncate text-sm text-[rgb(var(--faint))] xl:inline">
                {top.statement}
              </span>
            )}
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            {models.length > 0 && (
              <Listbox
                label="Model"
                value={current?.id ?? "default"}
                onChange={chooseModel}
                align="right"
                dataAttr="data-model-picker"
                buttonClassName="max-w-[11rem] text-xs sm:max-w-[16rem]"
                options={models.map((choice) => ({
                  value: choice.id,
                  label: choice.label,
                  hint:
                    choice.provider === "echo"
                      ? "Deterministic stub — no model is configured"
                      : choice.default
                        ? `Default · ${choice.provider}`
                        : `${choice.provider} · runs on the self-hosted box`,
                }))}
              />
            )}
            {turns.length > 0 && (
              <button
                type="button"
                onClick={() => update(incident.id, () => [])}
                disabled={busy}
                title="Start a new conversation about this incident"
                className="focusable hidden rounded-md border border-[rgb(var(--edge))] px-2.5 py-1.5 text-xs text-[rgb(var(--muted))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))] disabled:opacity-40 sm:inline-flex"
              >
                New chat
              </button>
            )}
            <button
              type="button"
              onClick={() => setContext((was) => !was)}
              aria-pressed={context}
              title="Show the incident's facts beside the conversation"
              className="focusable hidden rounded-md border border-[rgb(var(--edge))] px-2.5 py-1.5 text-xs text-[rgb(var(--muted))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))] xl:inline-flex"
            >
              {context ? "Hide facts" : "Show facts"}
            </button>
          </div>
        </header>

        <div ref={log} aria-live="polite" className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {turns.length === 0 && !busy ? (
              <Welcome incident={incident} onAsk={ask} busy={busy} />
            ) : (
              <div className="space-y-6">
                {turns.map((turn, index) => (
                  <TurnView key={index} turn={turn} incident={incident} />
                ))}
                {busy && <Waiting model={current?.label} />}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-[rgb(var(--edge))] bg-[rgb(var(--ground))] px-3 pb-4 pt-3 sm:px-6">
          {turns.length > 0 && (
            <div className="mx-auto mb-2 flex max-w-3xl gap-2 overflow-x-auto pb-1">
              {STARTERS.map((starter) => (
                <button
                  key={starter}
                  type="button"
                  disabled={busy}
                  onClick={() => ask(starter)}
                  className="focusable shrink-0 rounded-full border border-[rgb(var(--edge))] px-3 py-1 text-[11px] text-[rgb(var(--muted))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))] disabled:opacity-50"
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
            className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-2 shadow-lg transition focus-within:border-[rgb(var(--astra))]/60"
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
              maxLength={2000}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  ask(draft);
                }
              }}
              placeholder={`Ask about ${incident.id}…`}
              className="max-h-[33vh] min-h-[2.5rem] flex-1 resize-none bg-transparent px-2.5 py-2 text-[0.9375rem] leading-relaxed outline-none placeholder:text-[rgb(var(--faint))]"
            />
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              aria-label="Send"
              className="focusable inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[rgb(var(--astra))] text-[rgb(var(--ground))] transition hover:brightness-110 disabled:bg-[rgb(var(--raised))] disabled:text-[rgb(var(--faint))]"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>
          <p className="mx-auto mt-2 flex max-w-3xl flex-wrap justify-between gap-x-4 gap-y-1 px-1 text-[11px] text-[rgb(var(--faint))]">
            <span>Answers cite stored evidence. Sati cannot act — anything it proposes goes to a human.</span>
            <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
          </p>
        </div>
      </section>

      {context && (
        <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-[rgb(var(--edge))] bg-[rgb(var(--panel))]/60 xl:block">
          <Context incident={incident} />
        </aside>
      )}
    </div>
  );
}

/**
 * The empty screen, which is where a visitor decides whether to trust anything
 * that follows. So it says what the thing does and what it cannot do, then
 * offers the four questions an analyst actually asks, as large targets.
 */
function Welcome({
  incident,
  onAsk,
  busy,
}: {
  incident: Incident;
  onAsk: (question: string) => void;
  busy: boolean;
}) {
  return (
    <div className="flex min-h-[55vh] flex-col items-center justify-center py-6 text-center">
      <span className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-[rgb(var(--astra))]/40 bg-[rgb(var(--astra))]/10 text-[rgb(var(--astra))]">
        <Icon name="chat" className="h-7 w-7" />
      </span>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
        Ask Sati, the investigation agent
      </h1>
      <p className="mt-3 max-w-xl text-sm leading-relaxed text-[rgb(var(--muted))] sm:text-[0.9375rem]">
        It reads <span className="mono text-[rgb(var(--ink))]">{incident.id}</span> — the causal
        chain, the telemetry behind it and the plan — and answers from that. Every claim carries a
        citation you can follow. It cannot act: ask it to isolate a host and it names the action and
        sends it to a human for approval.
      </p>

      <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
        {STARTERS.map((starter, index) => (
          <button
            key={starter}
            type="button"
            disabled={busy}
            onClick={() => onAsk(starter)}
            className="focusable lift group rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-4 py-3.5 text-left transition hover:border-[rgb(var(--astra))]/50 disabled:opacity-50"
          >
            <span className="block text-sm font-medium text-[rgb(var(--ink))]">{starter}</span>
            <span className="mt-0.5 block text-xs text-[rgb(var(--faint))]">{STARTER_HINTS[index]}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** The incident's own facts, beside the conversation rather than inside it. */
function Context({ incident }: { incident: Incident }) {
  const top = incident.hypotheses[0];
  return (
    <div className="space-y-6 p-5 text-sm">
      <div>
        <p className="label mb-2">Diagnosis</p>
        <p className="leading-relaxed text-[rgb(var(--ink))]">
          {top ? top.statement : "No hypothesis recorded."}
        </p>
        {top && (
          <p className="mono mt-1.5 text-xs text-[rgb(var(--faint))]">
            <Stated value={top.confidence} />
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-3">
          <p className="label">Entities</p>
          <p className="tnum mt-1 text-xl font-semibold">{incident.impact.blast_radius_entities}</p>
        </div>
        <div className="rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-3">
          <p className="label">Users</p>
          <p className="tnum mt-1 text-xl font-semibold">{incident.impact.estimated_users_affected}</p>
        </div>
      </div>

      <div>
        <p className="label mb-2">Affected</p>
        <ul className="space-y-1">
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

      <Link
        href={`/incidents/${encodeURIComponent(incident.id)}`}
        className="focusable inline-flex items-center gap-1.5 rounded-md border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-xs transition hover:bg-[rgb(var(--raised))]"
      >
        Open the incident →
      </Link>
    </div>
  );
}

/**
 * While a turn is in flight: that it is working, for how long, and on which
 * model. It does not narrate stages it cannot see — retrieval happens on the
 * server and the hops arrive with the answer, so an invented progress sequence
 * would be the one thing this console is arranged against.
 */
function Waiting({ model }: { model?: string }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const tick = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(tick);
  }, []);

  return (
    <p data-waiting aria-live="polite" className="flex items-center gap-3 text-sm text-[rgb(var(--faint))]">
      <span className="loose" aria-hidden="true" />
      Reading the stored evidence
      {model && <span className="hidden text-xs sm:inline">· {model}</span>}
      {seconds >= 2 && <span className="tnum text-xs">{seconds}s</span>}
    </p>
  );
}
