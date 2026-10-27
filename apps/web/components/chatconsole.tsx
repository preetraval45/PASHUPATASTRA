"use client";

/**
 * Sati AI, full screen (RP-49), with conversation history and general questions.
 *
 * The left rail is the visitor's conversation history, like any chat app. Each
 * conversation has a scope: **General** — any question, cyber security or not,
 * answered from general knowledge with nothing from the estate behind it — or
 * **one incident**, answered only from that incident's stored evidence with
 * every claim cited. The scope is chosen per conversation and shown on it, so
 * a general answer can never be mistaken for a finding.
 *
 * Incident turns still render through `TurnView` (chat.tsx), so citations and
 * the withheld notice look exactly as they do on the incident page.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { TurnView, type Turn as IncidentTurn } from "@/components/chat";
import { Listbox } from "@/components/listbox";
import { Icon } from "@/components/sidebar";
import { Badge, Stated, statusForSeverity } from "@/components/ui";
import { askAgent, askGeneral, type GeneralAnswer, type Incident, type ModelChoice } from "@/lib/api";
import { MODELS } from "@/lib/navadurga";
import { servedName } from "@/lib/modelnames";

type Turn = IncidentTurn | { role: "general"; answer: GeneralAnswer };

type Conversation = {
  id: string;
  /** "general", or an incident id. */
  scope: string;
  title: string;
  turns: Turn[];
  updated: number;
};

const GENERAL = "general";
const STORE_KEY = "pashu.ask.conversations.v1";
const MODEL_KEY = "pashu.ask.model";
const KEEP_CONVERSATIONS = 50;
const KEEP_TURNS = 40;

/** The four incident starters are part of the answer-cache key — unchanged. */
const INCIDENT_STARTERS = [
  { q: "What happened?", hint: "The causal chain, in order" },
  { q: "How do we know — what is the evidence?", hint: "The evidence behind the diagnosis" },
  { q: "What is the blast radius?", hint: "Who and what is affected" },
  { q: "What should we do first?", hint: "A next step, routed through policy" },
];

const GENERAL_STARTERS = [
  { q: "How do I spot a phishing email?", hint: "Look-alike domains, links, urgency" },
  { q: "What is the difference between credential stuffing and password spraying?", hint: "Two attacks, two defences" },
  { q: "How should a small company prepare for ransomware?", hint: "Backups, access, a plan" },
  { q: "Explain MITRE ATT&CK in simple terms", hint: "Tactics, techniques, IDs" },
];

const AREA = Object.fromEntries(
  MODELS.map((m) => [m.name.toLowerCase(), { name: m.name, job: m.job.split(" — ")[0] }]),
);

function newId(): string {
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function load(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Conversation[]) : [];
  } catch {
    return [];
  }
}

function save(list: Conversation[]) {
  try {
    const trimmed = list
      .slice(0, KEEP_CONVERSATIONS)
      .map((c) => ({ ...c, turns: c.turns.slice(-KEEP_TURNS) }));
    localStorage.setItem(STORE_KEY, JSON.stringify(trimmed));
  } catch {
    // Not remembered; the conversation still works.
  }
}

function ago(ms: number): string {
  const s = Math.max(1, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

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
  const wantedIncident = params.get("incident");

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [pendingScope, setPendingScope] = useState<string>(wantedIncident ?? GENERAL);
  const [model, setModel] = useState<string>(models.find((m) => m.default)?.id ?? "default");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [facts, setFacts] = useState(true);

  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const stored = load();
    setConversations(stored);
    if (wantedIncident) {
      const existing = stored.find((c) => c.scope === wantedIncident);
      setActiveId(existing?.id ?? null);
      setPendingScope(wantedIncident);
    }
    try {
      const chosen = localStorage.getItem(MODEL_KEY);
      if (chosen && models.some((m) => m.id === chosen)) setModel(chosen);
    } catch {
      // Default model.
    }
    // Only on arrival; later URL changes are made by this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = conversations.find((c) => c.id === activeId) ?? null;
  const scope = active?.scope ?? pendingScope;
  const incident = scope === GENERAL ? null : (incidents.find((i) => i.id === scope) ?? null);
  const turns = active?.turns ?? [];

  const update = useCallback((next: Conversation[]) => {
    const sorted = [...next].sort((a, b) => b.updated - a.updated);
    save(sorted);
    setConversations(sorted);
  }, []);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [turns.length, busy, activeId]);

  useLayoutEffect(() => {
    const box = input.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, window.innerHeight / 3)}px`;
  }, [draft]);

  const go = useCallback(
    (nextScope: string) =>
      router.replace(nextScope === GENERAL ? "/ask" : `/ask?incident=${encodeURIComponent(nextScope)}`),
    [router],
  );

  const startNew = (nextScope: string = GENERAL) => {
    setActiveId(null);
    setPendingScope(nextScope);
    setDraft("");
    go(nextScope);
    input.current?.focus();
  };

  const chooseScope = (nextScope: string) => {
    if (active && active.turns.length > 0 && active.scope !== nextScope) startNew(nextScope);
    else {
      setPendingScope(nextScope);
      if (active) setActiveId(null);
      go(nextScope);
    }
  };

  const chooseModel = (id: string) => {
    setModel(id);
    try {
      localStorage.setItem(MODEL_KEY, id);
    } catch {
      // Not remembered.
    }
  };

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy) return;

      let convo = active;
      let list = conversations;
      if (!convo) {
        convo = { id: newId(), scope, title: text.slice(0, 80), turns: [], updated: Date.now() };
        list = [convo, ...conversations];
        setActiveId(convo.id);
      }
      const id = convo.id;
      update(
        list.map((c) =>
          c.id === id ? { ...c, turns: [...c.turns, { role: "you", text } as Turn], updated: Date.now() } : c,
        ),
      );
      setDraft("");
      setBusy(true);

      let reply: Turn;
      if (convo.scope === GENERAL) {
        const history: { question: string; answer: string }[] = [];
        const prior = convo.turns;
        for (let i = 0; i < prior.length - 1; i++) {
          const a = prior[i];
          const b = prior[i + 1];
          if (a.role === "you" && b.role === "general") history.push({ question: a.text, answer: b.answer.answer });
        }
        const result = await askGeneral(text, history, model);
        reply =
          "answer" in result
            ? { role: "general", answer: result.answer }
            : { role: "error", text: result.error, retryable: result.retryable };
      } else {
        const result = await askAgent(convo.scope, text, model);
        reply =
          "answer" in result
            ? { role: "sati", answer: result.answer }
            : { role: "error", text: result.error, retryable: result.retryable };
      }

      setConversations((current) => {
        const next = current
          .map((c) => (c.id === id ? { ...c, turns: [...c.turns, reply], updated: Date.now() } : c))
          .sort((a, b) => b.updated - a.updated);
        save(next);
        return next;
      });
      setBusy(false);
      input.current?.focus();
    },
    [active, busy, conversations, model, scope, update],
  );

  const remove = (id: string) => {
    update(conversations.filter((c) => c.id !== id));
    if (id === activeId) startNew(GENERAL);
  };

  const current = models.find((m) => m.id === model) ?? models[0];
  const scopeOptions = useMemo(
    () => [
      {
        value: GENERAL,
        label: "General — any question",
        hint: "Cyber security or anything else; general knowledge, nothing from your systems",
      },
      ...incidents.map((i) => ({
        value: i.id,
        label: (
          <span className="mono">
            {i.id} · {i.severity}
          </span>
        ),
        hint: i.hypotheses[0]?.statement,
      })),
    ],
    [incidents],
  );

  return (
    <div className="flex min-h-0 flex-1">
      {/* History — every conversation this browser has had with Sati. */}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-[rgb(var(--edge))] bg-[rgb(var(--panel))]/60 lg:flex">
        <div className="shrink-0 border-b border-[rgb(var(--edge))] p-3">
          <button
            type="button"
            onClick={() => startNew(GENERAL)}
            data-new-chat
            className="focusable flex w-full items-center justify-center gap-2 rounded-lg bg-[rgb(var(--astra))] px-3 py-2 text-sm font-medium text-[rgb(var(--ground))] transition hover:brightness-110"
          >
            <span aria-hidden="true">+</span> New chat
          </button>
        </div>
        <p className="label px-4 pb-1 pt-3">History</p>
        <ul data-history className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {conversations.length === 0 && (
            <li className="px-2 py-3 text-xs leading-relaxed text-[rgb(var(--faint))]">
              Your conversations appear here. They are kept in this browser only.
            </li>
          )}
          {conversations.map((c) => (
            <li key={c.id} className="group relative">
              <button
                type="button"
                onClick={() => {
                  setActiveId(c.id);
                  go(c.scope);
                }}
                aria-current={c.id === activeId ? "true" : undefined}
                className={`focusable w-full rounded-lg px-3 py-2 pr-8 text-left transition ${
                  c.id === activeId ? "bg-[rgb(var(--raised))]" : "hover:bg-[rgb(var(--raised))]"
                }`}
              >
                <span className="block truncate text-sm text-[rgb(var(--ink))]">{c.title}</span>
                <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-[rgb(var(--faint))]">
                  <span className={c.scope === GENERAL ? "" : "mono"}>{c.scope === GENERAL ? "General" : c.scope}</span>
                  <span>·</span>
                  <span>{ago(c.updated)}</span>
                </span>
              </button>
              <button
                type="button"
                onClick={() => remove(c.id)}
                aria-label={`Delete conversation: ${c.title}`}
                className="focusable absolute right-1.5 top-2 hidden rounded px-1.5 text-[rgb(var(--faint))] hover:text-[rgb(var(--crit))] group-hover:block group-focus-within:block"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        {allowance && <div className="shrink-0 border-t border-[rgb(var(--edge))] px-4 py-3">{allowance}</div>}
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-[rgb(var(--edge))] px-3 sm:gap-3 sm:px-4">
          <button
            type="button"
            onClick={() => startNew(GENERAL)}
            aria-label="New chat"
            className="focusable inline-flex h-8 w-8 items-center justify-center rounded-md border border-[rgb(var(--edge))] text-[rgb(var(--muted))] lg:hidden"
          >
            +
          </button>
          <div className="min-w-0">
            <Listbox
              label="What to ask about"
              value={scope}
              onChange={chooseScope}
              dataAttr="data-ask-scope"
              buttonClassName="text-xs"
              options={scopeOptions}
            />
          </div>
          {incident && (
            <span className="hidden xl:inline-flex">
              <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
            </span>
          )}

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
                    choice.description ||
                    (choice.provider === "echo"
                      ? "Deterministic stub — no model is configured"
                      : choice.default
                        ? "Default"
                        : "Runs on the self-hosted box"),
                }))}
              />
            )}
            {incident && (
              <button
                type="button"
                onClick={() => setFacts((was) => !was)}
                aria-pressed={facts}
                className="focusable hidden rounded-md border border-[rgb(var(--edge))] px-2.5 py-1.5 text-xs text-[rgb(var(--muted))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))] xl:inline-flex"
              >
                {facts ? "Hide facts" : "Show facts"}
              </button>
            )}
          </div>
        </header>

        <div ref={log} aria-live="polite" className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {turns.length === 0 && !busy ? (
              <Welcome incident={incident} onAsk={ask} busy={busy} />
            ) : (
              <div className="space-y-6">
                {turns.map((turn, index) =>
                  turn.role === "general" ? (
                    <GeneralTurn key={index} answer={turn.answer} />
                  ) : turn.role === "sati" && !incident ? null : (
                    <TurnView key={index} turn={turn} incident={(incident ?? incidents[0]) as Incident} />
                  ),
                )}
                {busy && <Waiting model={current?.label} general={!incident} />}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-[rgb(var(--edge))] bg-[rgb(var(--ground))] px-3 pb-4 pt-3 sm:px-6">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              ask(draft);
            }}
            className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-2 shadow-lg transition focus-within:border-[rgb(var(--astra))]/60"
          >
            <label htmlFor="ask-question" className="sr-only">
              {incident ? `Your question about ${incident.id}` : "Your question"}
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
              placeholder={incident ? `Ask about ${incident.id}…` : "Ask Sati anything — cyber security or otherwise…"}
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
            <span>
              {incident
                ? "Answers come from this incident's stored evidence, with citations. Sati cannot act."
                : "General knowledge, not your systems. Sati cannot act, and won't help attack anyone."}
            </span>
            <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
          </p>
        </div>
      </section>

      {incident && facts && (
        <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-[rgb(var(--edge))] bg-[rgb(var(--panel))]/60 xl:block">
          <Context incident={incident} />
        </aside>
      )}
    </div>
  );
}

/** A general answer: which Navadurga area it was routed to, the answer, and
 *  plainly that it is general knowledge rather than a finding. */
function GeneralTurn({ answer }: { answer: GeneralAnswer }) {
  const area = AREA[answer.area];
  return (
    <div data-turn="general" className="max-w-[95%] space-y-2">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
        <span aria-hidden="true" className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[rgb(var(--astra))]" />
        <span className="font-medium text-[rgb(var(--astra))]">Sati</span>
        {area && (
          <span className="text-[rgb(var(--muted))]" title="The specialist area this question was routed to (adr/Navadurga)">
            · {area.name} area — {area.job.toLowerCase()}
          </span>
        )}
      </p>
      <p
        data-answer
        className={
          answer.declined
            ? "whitespace-pre-wrap rounded-lg border border-dashed border-[rgb(var(--edge))] px-3 py-2 text-sm leading-relaxed text-[rgb(var(--muted))]"
            : "whitespace-pre-wrap border-l-2 border-[rgb(var(--astra))]/40 pl-3 text-[0.9375rem] leading-relaxed"
        }
      >
        {answer.answer}
      </p>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[rgb(var(--faint))]">
        <Badge status="neutral">general knowledge — not from your evidence</Badge>
        {answer.declined && <Badge status="warning">declined</Badge>}
        <span>{answer.tokens} tokens</span>
        <span className="mono">{servedName(answer.model)}</span>
      </p>
    </div>
  );
}

function Welcome({
  incident,
  onAsk,
  busy,
}: {
  incident: Incident | null;
  onAsk: (question: string) => void;
  busy: boolean;
}) {
  const starters = incident ? INCIDENT_STARTERS : GENERAL_STARTERS;
  return (
    <div className="flex min-h-[55vh] flex-col items-center justify-center py-6 text-center">
      <span className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-[rgb(var(--astra))]/40 bg-[rgb(var(--astra))]/10 text-[rgb(var(--astra))]">
        <Icon name="chat" className="h-7 w-7" />
      </span>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Sati AI</h1>
      {incident ? (
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-[rgb(var(--muted))] sm:text-[0.9375rem]">
          Sati, the investigation agent, reads <span className="mono text-[rgb(var(--ink))]">{incident.id}</span>{" "}
          — the causal chain, the telemetry behind it and the plan — and answers from that, citing every
          claim. It cannot act: anything it proposes goes to a human.
        </p>
      ) : (
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-[rgb(var(--muted))] sm:text-[0.9375rem]">
          Ask Sati, the investigation agent, anything — cyber security or not. Each question is routed to
          one of nine specialist areas, from network threats to recovery. Pick an incident above to get
          answers from its evidence instead.
        </p>
      )}

      <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
        {starters.map((s) => (
          <button
            key={s.q}
            type="button"
            disabled={busy}
            onClick={() => onAsk(s.q)}
            className="focusable lift rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-4 py-3.5 text-left transition hover:border-[rgb(var(--astra))]/50 disabled:opacity-50"
          >
            <span className="block text-sm font-medium text-[rgb(var(--ink))]">{s.q}</span>
            <span className="mt-0.5 block text-xs text-[rgb(var(--faint))]">{s.hint}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Context({ incident }: { incident: Incident }) {
  const top = incident.hypotheses[0];
  return (
    <div className="space-y-6 p-5 text-sm">
      <div>
        <p className="label mb-2">Diagnosis</p>
        <p className="leading-relaxed text-[rgb(var(--ink))]">{top ? top.statement : "No hypothesis recorded."}</p>
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

function Waiting({ model, general }: { model?: string; general: boolean }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const tick = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(tick);
  }, []);
  return (
    <p data-waiting aria-live="polite" className="flex items-center gap-3 text-sm text-[rgb(var(--faint))]">
      <span className="loose" aria-hidden="true" />
      {general ? "Thinking" : "Reading the stored evidence"}
      {model && <span className="hidden text-xs sm:inline">· {model}</span>}
      {seconds >= 2 && <span className="tnum text-xs">{seconds}s</span>}
    </p>
  );
}
