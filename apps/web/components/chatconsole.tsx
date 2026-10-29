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

import { AnswerText, defendFollowUp } from "@/components/answertext";
import { TurnView, type Turn as IncidentTurn } from "@/components/chat";
import { examplesFor, runSpecialist, specialist, SPECIALISTS, type Example } from "@/components/specialists";
import { Listbox } from "@/components/listbox";
import { Icon } from "@/components/sidebar";
import { Badge, Stated, statusForSeverity } from "@/components/ui";
import { askAgent, askGeneral, type GeneralAnswer, type Incident, type ModelChoice } from "@/lib/api";
import { MODELS } from "@/lib/navadurga";
import { servedName } from "@/lib/modelnames";

type Turn =
  | IncidentTurn
  | { role: "general"; answer: GeneralAnswer }
  /** A data-reading model run on a held-out example (components/specialists.tsx). */
  | { role: "specialist"; form: string; text: string };

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
const SPECIALIST_KEY = "pashu.ask.specialist";
const KEEP_CONVERSATIONS = 50;
const KEEP_TURNS = 40;

/** The four incident starters are part of the answer-cache key — unchanged. */
const INCIDENT_STARTERS = [
  { q: "What happened?", hint: "The causal chain, in order" },
  { q: "How do we know — what is the evidence?", hint: "The evidence behind the diagnosis" },
  { q: "What is the blast radius?", hint: "Who and what is affected" },
  { q: "What should we do first?", hint: "A next step, routed through policy" },
];

/** Questions Sati's own models answer well today, each showing a different one at work. Chosen by
 *  asking them of the served models (28 Oct 2026); broader questions wait for Kushmanda. */
const GENERAL_STARTERS = [
  { q: "Which ATT&CK technique is it when an attacker schedules a task to run their malware at every logon?", hint: "Brahmacharini names the technique" },
  { q: "How do we defend against phishing emails?", hint: "ATT&CK's defences, ordered by Skandamata" },
  { q: "What should we do about Log4Shell (CVE-2021-44228)?", hint: "CISA's required action, cited" },
  { q: "What is credential stuffing?", hint: "The attack pattern, explained and cited" },
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
  const [special, setSpecial] = useState("auto");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [examples, setExamples] = useState<Example[] | null | undefined>(undefined);

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
    try {
      const kept = localStorage.getItem(SPECIALIST_KEY);
      if (kept && SPECIALISTS.some((s) => s.id === kept)) setSpecial(kept);
    } catch {
      // Sati, all-round.
    }
    // A link that names a model ("/ask?model=sati:skandamata") picks it for this visit.
    const linked = params.get("model");
    if (linked && models.some((m) => m.id === linked)) setModel(linked);
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

  const chooseSpecialist = (id: string) => {
    const s = specialist(id);
    setSpecial(s.id);
    try {
      localStorage.setItem(SPECIALIST_KEY, s.id);
    } catch {
      // Not remembered.
    }
    if (s.kind === "ask" && s.model) chooseModel(s.model);
    if (s.kind === "auto") chooseModel(models.find((m) => m.default)?.id ?? "default");
  };

  const chosen = specialist(special);
  useEffect(() => {
    if (!["tree", "cases", "servers"].includes(chosen.kind)) {
      setExamples(undefined);
      return;
    }
    let live = true;
    setExamples(undefined);
    examplesFor(chosen).then((list) => live && setExamples(list));
    return () => {
      live = false;
    };
  }, [chosen]);

  /** Runs a data-reading specialist on one held-out example, as a turn in the conversation. */
  const runExample = useCallback(
    async (example: Example) => {
      if (busy) return;
      const s = chosen;
      const text = `Run ${s.name} on ${example.label === example.id ? example.id : `${example.id} (${example.label})`}`;
      let convo = active && active.scope === GENERAL ? active : null;
      let list = conversations;
      if (!convo) {
        convo = { id: newId(), scope: GENERAL, title: text.slice(0, 80), turns: [], updated: Date.now() };
        list = [convo, ...conversations];
        setActiveId(convo.id);
        setPendingScope(GENERAL);
      }
      const id = convo.id;
      update(list.map((c) => (c.id === id ? { ...c, turns: [...c.turns, { role: "you", text } as Turn], updated: Date.now() } : c)));
      setBusy(true);
      const result = await runSpecialist(s, example.id);
      const reply: Turn = result
        ? { role: "specialist", form: s.id, text: result }
        : { role: "error", text: `${s.name} is not reachable right now.`, retryable: true };
      setConversations((current) => {
        const next = current
          .map((c) => (c.id === id ? { ...c, turns: [...c.turns, reply], updated: Date.now() } : c))
          .sort((a, b) => b.updated - a.updated);
        save(next);
        return next;
      });
      setBusy(false);
    },
    [active, busy, chosen, conversations, update],
  );

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

      {historyOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Conversation history">
          <button type="button" aria-label="Close history" onClick={() => setHistoryOpen(false)} className="absolute inset-0 bg-black/50" />
          <div className="rise absolute inset-x-0 bottom-0 flex max-h-[75vh] flex-col rounded-t-3xl border-t border-[rgb(var(--edge))] bg-[rgb(var(--panel))] pb-[env(safe-area-inset-bottom)] shadow-2xl">
            <div className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-[rgb(var(--edge-strong))]" aria-hidden="true" />
            <div className="flex items-center justify-between px-4 pb-2 pt-3">
              <p className="font-semibold">History</p>
              <button
                type="button"
                onClick={() => {
                  setHistoryOpen(false);
                  startNew(GENERAL);
                }}
                className="focusable rounded-lg bg-[rgb(var(--astra))] px-3 py-1.5 text-sm font-medium text-[rgb(var(--ground))]"
              >
                + New chat
              </button>
            </div>
            <ul className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
              {conversations.length === 0 && (
                <li className="px-2 py-4 text-sm text-[rgb(var(--faint))]">No conversations yet. They are kept on this device only.</li>
              )}
              {conversations.map((c) => (
                <li key={c.id} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveId(c.id);
                      go(c.scope);
                      setHistoryOpen(false);
                    }}
                    className={`focusable min-w-0 flex-1 rounded-xl px-3 py-2.5 text-left ${c.id === activeId ? "bg-[rgb(var(--raised))]" : ""}`}
                  >
                    <span className="block truncate text-sm">{c.title}</span>
                    <span className="text-[11px] text-[rgb(var(--faint))]">
                      {c.scope === GENERAL ? "General" : c.scope} · {ago(c.updated)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(c.id)}
                    aria-label={`Delete conversation: ${c.title}`}
                    className="focusable h-10 w-10 shrink-0 rounded-lg text-[rgb(var(--faint))] hover:text-[rgb(var(--crit))]"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

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
          {/* Below lg the history sidebar is hidden; this opens it as a sheet, so past chats stay reachable on a phone. */}
          <button
            type="button"
            onClick={() => setHistoryOpen(true)}
            aria-label={`History, ${conversations.length} conversation${conversations.length === 1 ? "" : "s"}`}
            className="focusable inline-flex h-8 items-center gap-1.5 rounded-md border border-[rgb(var(--edge))] px-2 text-xs text-[rgb(var(--muted))] lg:hidden"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {conversations.length > 0 && <span className="tnum">{conversations.length}</span>}
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
              <Welcome
                incident={incident}
                onAsk={ask}
                busy={busy}
                special={special}
                onSpecialist={chooseSpecialist}
                examples={examples}
                onExample={runExample}
              />
            ) : (
              <div className="space-y-6">
                {turns.map((turn, index) =>
                  turn.role === "general" ? (
                    <GeneralTurn
                      key={index}
                      answer={turn.answer}
                      onAsk={index === turns.length - 1 && !busy ? ask : undefined}
                    />
                  ) : turn.role === "specialist" ? (
                    <SpecialistTurn key={index} form={turn.form} text={turn.text} />
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
          {!incident && (
            <div className="mx-auto mb-2 max-w-3xl space-y-2">
              <div role="tablist" aria-label="Specialist" className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
                {SPECIALISTS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    role="tab"
                    aria-selected={special === s.id}
                    onClick={() => chooseSpecialist(s.id)}
                    title={s.job}
                    className={`focusable shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition ${
                      special === s.id
                        ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))] text-[rgb(var(--ground))]"
                        : "border-[rgb(var(--edge-strong))] text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
                    }`}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
              {turns.length > 0 && examples && examples.length > 0 && (
                <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
                  <span className="shrink-0 self-center text-[11px] text-[rgb(var(--faint))]">Run on:</span>
                  {examples.slice(0, 12).map((e) => (
                    <button
                      key={e.id}
                      type="button"
                      disabled={busy}
                      onClick={() => runExample(e)}
                      className="focusable shrink-0 rounded-lg border border-[rgb(var(--edge))] px-2.5 py-1 text-xs text-[rgb(var(--muted))] transition hover:border-[rgb(var(--astra))]/60 hover:text-[rgb(var(--ink))] disabled:opacity-50"
                    >
                      {e.id}
                    </button>
                  ))}
                </div>
              )}
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
function GeneralTurn({ answer, onAsk }: { answer: GeneralAnswer; onAsk?: (question: string) => void }) {
  const area = AREA[answer.area];
  const followUp = !answer.declined ? defendFollowUp(answer.answer) : null;
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
      <div
        data-answer
        className={
          answer.declined
            ? "rounded-lg border border-dashed border-[rgb(var(--edge))] px-3 py-2"
            : "rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-4 py-3.5"
        }
      >
        <AnswerText text={answer.answer} muted={answer.declined} />
        <AnswerActions text={answer.answer} />
      </div>
      {followUp && onAsk && (
        <button
          type="button"
          onClick={() => onAsk(followUp)}
          className="focusable rise inline-flex max-w-full items-center gap-2 rounded-full border border-[rgb(var(--astra))]/40 bg-[rgb(var(--astra))]/5 px-3.5 py-1.5 text-left text-sm text-[rgb(var(--ink))] transition hover:bg-[rgb(var(--astra))]/10"
        >
          <span aria-hidden="true" className="text-[rgb(var(--astra))]">↳</span>
          <span className="min-w-0">{followUp}</span>
        </button>
      )}
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[rgb(var(--faint))]">
        <Badge status="neutral">general knowledge — not from your evidence</Badge>
        {answer.declined && <Badge status="warning">declined</Badge>}
        <span>{answer.tokens} tokens</span>
        <span className="mono">{servedName(answer.model)}</span>
      </p>
    </div>
  );
}

/** A data-reading model's verdict on a held-out example. */
function SpecialistTurn({ form, text }: { form: string; text: string }) {
  const s = specialist(form);
  return (
    <div data-turn="specialist" className="max-w-[95%] space-y-2">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
        <span aria-hidden="true" className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[rgb(var(--astra))]" />
        <span className="font-medium text-[rgb(var(--astra))]">{s.name}</span>
        <span className="text-[rgb(var(--muted))]">· {s.job.toLowerCase()}</span>
      </p>
      <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-4 py-3.5">
        <AnswerText text={text} />
        <p className="mt-3 border-t border-[rgb(var(--edge))] pt-2 text-[11px] text-[rgb(var(--faint))]">
          Run live on an example it never trained on, with the truth beside the answer.
        </p>
      </div>
    </div>
  );
}

/** Copy the answer, or share it: Android's share sheet inside the app, the system one elsewhere. */
function AnswerActions({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard blocked: nothing to undo.
    }
  };
  const share = async () => {
    const app = (window as { PashupatastraApp?: { share?: (title: string, url: string) => void } }).PashupatastraApp;
    const body = `${text}

— Sati, the investigation agent · ${window.location.origin}/ask`;
    if (app?.share) return app.share("Sati AI", body);
    if (navigator.share) {
      try {
        await navigator.share({ title: "Sati AI", text: body });
      } catch {
        // Dismissed.
      }
    } else {
      copy();
    }
  };
  return (
    <p className="mt-3 flex gap-1 border-t border-[rgb(var(--edge))] pt-2">
      {(
        [
          [copied ? "Copied" : "Copy", copy],
          ["Share", share],
        ] as const
      ).map(([label, action]) => (
        <button
          key={label === "Copied" ? "Copy" : label}
          type="button"
          onClick={action}
          className="focusable rounded-md px-2 py-1 text-xs text-[rgb(var(--faint))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
        >
          {label}
        </button>
      ))}
    </p>
  );
}

function Welcome({
  incident,
  onAsk,
  busy,
  special = "auto",
  onSpecialist,
  examples,
  onExample,
}: {
  incident: Incident | null;
  onAsk: (question: string) => void;
  busy: boolean;
  special?: string;
  onSpecialist?: (id: string) => void;
  examples?: Example[] | null;
  onExample?: (example: Example) => void;
}) {
  if (incident) {
    return (
      <div className="flex min-h-[55vh] flex-col items-center justify-center py-6 text-center">
        <span className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-[rgb(var(--astra))]/40 bg-[rgb(var(--astra))]/10 text-[rgb(var(--astra))]">
          <Icon name="chat" className="h-7 w-7" />
        </span>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Sati AI</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-[rgb(var(--muted))] sm:text-[0.9375rem]">
          Sati, the investigation agent, reads <span className="mono text-[rgb(var(--ink))]">{incident.id}</span>{" "}
          — the causal chain, the telemetry behind it and the plan — and answers from that, citing every
          claim. It cannot act: anything it proposes goes to a human.
        </p>
        <Starters starters={INCIDENT_STARTERS} onAsk={onAsk} busy={busy} />
      </div>
    );
  }

  const chosen = specialist(special);
  return (
    <div className="space-y-6 py-2">
      <div className="relative isolate overflow-hidden rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-5 py-6 sm:px-7">
        <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-10" />
        <p className="label text-[rgb(var(--astra))]">Sati AI</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Nine specialists, one investigation agent</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          Sati, the investigation agent, runs on nine models built and trained in this project. Ask a question, or pick a
          specialist and run it on real data it never trained on — every answer shows the truth beside it, and none uses an
          outside AI.
        </p>
      </div>

      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {SPECIALISTS.map((s) => {
          const active = s.id === chosen.id;
          const tag = s.kind === "auto" || s.kind === "ask" ? "answers questions" : s.kind === "private" ? "not public yet" : "runs on data";
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSpecialist?.(s.id)}
                aria-pressed={active}
                className={`focusable lift flex h-full w-full flex-col rounded-xl border p-3 text-left transition ${
                  active
                    ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))]/10 shadow-sm"
                    : "border-[rgb(var(--edge))] bg-[rgb(var(--panel))] hover:border-[rgb(var(--astra))]/50"
                }`}
              >
                <span className="flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 rounded-full ${s.kind === "private" ? "bg-[rgb(var(--faint))]" : "bg-[rgb(var(--ok))]"}`}
                  />
                  <span className="text-sm font-semibold">{s.name}</span>
                </span>
                <span className="mt-1 text-xs leading-snug text-[rgb(var(--muted))]">{s.job}</span>
                <span className="mt-auto pt-2 text-[10.5px] uppercase tracking-wide text-[rgb(var(--faint))]">{tag}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="rise" key={chosen.id}>
        {chosen.kind === "private" ? (
          <p className="rounded-xl border border-dashed border-[rgb(var(--edge-strong))] p-4 text-sm leading-relaxed text-[rgb(var(--muted))]">
            Kushmanda, Sati&apos;s own language model, writes answers in its own words from the passages the other models
            find. Its weights are kept private for now, so it does not answer on this site yet. Its measured results are on{" "}
            <Link href="/models#kushmanda-results" className="text-[rgb(var(--astra))] hover:underline">the models page</Link>.
          </p>
        ) : chosen.kind === "auto" || chosen.kind === "ask" ? (
          <Starters
            starters={
              chosen.id === "skandamata"
                ? GENERAL_STARTERS.filter((x) => /defend/i.test(x.q))
                : chosen.id === "brahmacharini"
                  ? GENERAL_STARTERS.filter((x) => /technique|what is/i.test(x.q))
                  : GENERAL_STARTERS
            }
            onAsk={onAsk}
            busy={busy}
          />
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-[rgb(var(--muted))]">
              Pick {chosen.pick}. {chosen.name} runs on it live, and the answer says whether it was right.
            </p>
            {examples === undefined ? (
              <div className="grid gap-2 sm:grid-cols-3">
                {Array.from({ length: 6 }, (_, i) => (
                  <div key={i} className="h-14 animate-pulse rounded-xl bg-[rgb(var(--raised))]" />
                ))}
              </div>
            ) : examples === null || examples.length === 0 ? (
              <p className="text-sm text-[rgb(var(--faint))]">The live model is not reachable right now.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-3">
                {examples.slice(0, 12).map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    disabled={busy}
                    onClick={() => onExample?.(e)}
                    className="focusable lift rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-3.5 py-2.5 text-left transition hover:border-[rgb(var(--astra))]/50 disabled:opacity-50"
                  >
                    <span className="mono block truncate text-sm text-[rgb(var(--ink))]">{e.id}</span>
                    <span className="block truncate text-xs text-[rgb(var(--faint))]">{e.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Starters({
  starters,
  onAsk,
  busy,
}: {
  starters: readonly { q: string; hint: string }[];
  onAsk: (question: string) => void;
  busy: boolean;
}) {
  return (
    <div className="mx-auto mt-2 grid w-full max-w-3xl gap-3 sm:grid-cols-2">
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
