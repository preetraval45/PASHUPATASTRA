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
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { useAccount } from "@/components/account";
import { AnswerText } from "@/components/answertext";
import { TurnView, type Turn as IncidentTurn } from "@/components/chat";
import { examplesFor, runSpecialist, served, specialist, SPECIALISTS, type Example, type Specialist, type Verdict } from "@/components/specialists";
import { Icon } from "@/components/sidebar";
import { Badge, Stated, statusForSeverity } from "@/components/ui";
import { askAgent, askGeneral, type GeneralAnswer, type Incident, type ModelChoice } from "@/lib/api";
import { MODELS } from "@/lib/navadurga";
import { servedName } from "@/lib/modelnames";
import { followUps } from "@/lib/answerlinks";
import { historyGroups } from "@/lib/historygroups";
import { hue } from "@/lib/hues";

type Turn =
  | IncidentTurn
  | { role: "general"; answer: GeneralAnswer }
  /** A data-reading model run on a held-out example (components/specialists.tsx). */
  | { role: "specialist"; form: string; text: string; verdict?: Verdict };

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

/** Questions the served models answer well, each a different kind: what an attack is, how to defend,
 *  which technique, what to do about a CVE. Checked against the served models (1 Nov 2026). */
const GENERAL_STARTERS = [
  { q: "What is credential stuffing?", hint: "What it is, and how to defend against it" },
  { q: "How do we defend against ransomware?", hint: "Defences, most relevant first" },
  { q: "Which ATT&CK technique is it when an attacker schedules a task to run their malware at every logon?", hint: "Names the technique" },
  { q: "What should we do about Log4Shell?", hint: "CISA's required action, cited" },
  { q: "What is SQL injection?", hint: "The attack, and the fixes that stop it" },
  { q: "How do we defend against phishing emails?", hint: "Training first, then the controls" },
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
  const [find, setFind] = useState("");
  const [examples, setExamples] = useState<Example[] | null | undefined>(undefined);
  // The reply that has just arrived, as "<conversation>:<turn index>": only it is streamed in.
  const [streaming, setStreaming] = useState<string | null>(null);

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
    // The model follows the specialist: Sati (the default) routes each question to the right model
    // itself; picking Brahmacharini or Skandamata asks that one alone. There is no separate picker.
    try {
      const kept = localStorage.getItem(SPECIALIST_KEY);
      if (kept && SPECIALISTS.some((s) => s.id === kept)) {
        setSpecial(kept);
        const s = specialist(kept);
        if (s.kind === "ask" && s.model && models.some((m) => m.id === s.model)) setModel(s.model);
      }
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

  const chooseModel = (id: string) => setModel(id);

  const modelIds = models.map((m) => m.id);
  const chooseSpecialist = (id: string) => {
    const s = served(specialist(id), modelIds);
    setSpecial(s.id);
    try {
      localStorage.setItem(SPECIALIST_KEY, s.id);
    } catch {
      // Not remembered.
    }
    if (s.kind === "ask" && s.model) chooseModel(s.model);
    if (s.kind === "auto") chooseModel(models.find((m) => m.default)?.id ?? "default");
  };

  const modelKey = modelIds.join(",");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const chosen = useMemo(() => served(specialist(special), modelIds), [special, modelKey]);
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
        ? { role: "specialist", form: s.id, text: result.text, verdict: result.verdict }
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
      const replyAt = convo.turns.length + 1;
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

      setStreaming(`${id}:${replyAt}`);
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

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
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
        <div className="px-3 pt-3">
          <label className="relative block">
            <span className="sr-only">Search conversations</span>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[rgb(var(--faint))]" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>
            <input
              value={find}
              onChange={(e) => setFind(e.target.value)}
              placeholder="Search chats"
              className="w-full rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] py-1.5 pl-8 pr-2 text-xs outline-none focus:border-[rgb(var(--astra))]/60"
            />
          </label>
        </div>
        <div data-history className="flex-1 overflow-y-auto px-2 pb-2 pt-1">
          {conversations.length === 0 && (
            <p className="px-2 py-3 text-xs leading-relaxed text-[rgb(var(--faint))]">
              Your conversations appear here. They are kept in this browser only.
            </p>
          )}
          {conversations.length > 0 && find && historyGroups(conversations, Date.now(), find).length === 0 && (
            <p className="px-2 py-3 text-xs text-[rgb(var(--faint))]">No chats match “{find}”.</p>
          )}
          {historyGroups(conversations, Date.now(), find).map((group) => (
            <div key={group.label} className="mt-2">
              <p className="px-2 pb-1 text-[11px] font-medium text-[rgb(var(--faint))]">{group.label}</p>
              <ul className="space-y-0.5">
                {group.items.map((c) => (
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
            </div>
          ))}
        </div>
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
          {incident ? (
            <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-[rgb(var(--edge))] py-1 pl-2.5 pr-1 text-xs">
              <span className="text-[rgb(var(--muted))]">About</span>
              <span className="mono truncate">{incident.id}</span>
              <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
              <button
                type="button"
                onClick={() => chooseScope(GENERAL)}
                aria-label="Stop asking about this incident"
                className="focusable inline-flex h-6 w-6 items-center justify-center rounded-full text-[rgb(var(--faint))] hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
              >
                ×
              </button>
            </span>
          ) : (
            <p className="min-w-0 truncate text-sm">
              <span className="font-semibold">Sati AI</span>
              <span className="hidden text-[rgb(var(--faint))] sm:inline">
                {" "}· {special === "auto" ? "picks the right model for each question" : `asking ${specialist(special).name}`}
              </span>
            </p>
          )}

          <div className="ml-auto flex shrink-0 items-center gap-2">
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
                modelIds={modelIds}
              />
            ) : (
              <div className="space-y-8">
                {turns.map((turn, index) =>
                  turn.role === "general" ? (
                    <GeneralTurn
                      key={index}
                      answer={turn.answer}
                      stream={streaming === `${activeId}:${index}`}
                      onAsk={index === turns.length - 1 && !busy ? ask : undefined}
                    />
                  ) : turn.role === "specialist" ? (
                    <SpecialistTurn key={index} form={turn.form} text={turn.text} verdict={turn.verdict} />
                  ) : turn.role === "sati" && !incident ? null : (
                    <TurnView key={index} turn={turn} incident={(incident ?? incidents[0]) as Incident} />
                  ),
                )}
                {busy && <Waiting model={current?.label} general={!incident} />}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-[rgb(var(--edge))] bg-[rgb(var(--ground))] px-3 pb-2.5 pt-2.5 sm:px-6">
          {!incident && (
            <div className="mx-auto mb-2 max-w-3xl space-y-2">
              <div role="tablist" aria-label="Specialist" className="no-scrollbar fade-x -mx-1 flex gap-1.5 overflow-x-auto px-3 pb-1">
                {SPECIALISTS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    role="tab"
                    aria-selected={special === s.id}
                    onClick={() => chooseSpecialist(s.id)}
                    title={s.job}
                    style={hueOf(s)}
                    className={`focusable inline-flex shrink-0 items-center gap-1.5 rounded-full border py-1 pl-1 pr-3 text-xs font-medium transition ${
                      special === s.id
                        ? "sp-card text-[rgb(var(--ink))]"
                        : "sp-hover border-[rgb(var(--edge))] text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
                    }`}
                  >
                    <Monogram s={s} size="xs" />
                    {s.name}
                  </button>
                ))}
              </div>
              {turns.length > 0 && examples && examples.length > 0 && (
                <div className="no-scrollbar fade-x -mx-1 flex gap-1.5 overflow-x-auto px-3 pb-1">
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
            className="mx-auto flex max-w-3xl items-end gap-2 rounded-3xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-2 pl-3 shadow-[0_8px_30px_-12px_rgb(0_0_0/0.5)] transition focus-within:border-[rgb(var(--astra))]/60 focus-within:shadow-[0_8px_30px_-10px_rgb(var(--astra)/0.35)]"
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
              placeholder={incident ? `Ask about ${incident.id}…` : "Ask about an attack, a technique, a defence or a CVE…"}
              className="max-h-[33vh] min-h-[2.5rem] flex-1 resize-none bg-transparent px-2.5 py-2 text-[0.9375rem] leading-relaxed outline-none placeholder:text-[rgb(var(--faint))]"
            />
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              aria-label="Send"
              className="focusable inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--astra))] text-[rgb(var(--ground))] transition hover:scale-105 hover:brightness-110 disabled:scale-100 disabled:bg-[rgb(var(--raised))] disabled:text-[rgb(var(--faint))]"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>
          {/* One quiet line. The privacy notice stays visible because it is a disclosure: questions are
              kept in the public audit trail (services/api routes._asked) with no name attached, and
              /privacy says so too. The rest of the fine print is one tap away. */}
          <details className="group mx-auto mt-1.5 max-w-3xl px-1 text-[11px] text-[rgb(var(--faint))]">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 [&::-webkit-details-marker]:hidden">
              <span className="min-w-0 truncate">
                Questions are public in the <a href="/audit" className="underline">audit trail</a>, so leave out personal details
              </span>
              <span
                aria-label="More about Sati AI"
                className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--edge-strong))] text-[9px] group-open:bg-[rgb(var(--raised))]"
              >
                i
              </span>
            </summary>
            <p className="mt-1">
              {incident
                ? "Answers come from this incident's stored evidence, with citations. Sati cannot act."
                : "General knowledge, not your systems. Sati cannot act, and won't help attack anyone."}
              <span className="hidden sm:inline"> Enter to send · Shift+Enter for a new line.</span>
            </p>
          </details>
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

/** The models an answer actually drew on, read from what it contains: the one it was routed to, Skandamata
 *  when it lists defences, Brahmacharini when it explains or ranks what retrieval found. */
function consulted(answer: GeneralAnswer): string[] {
  if (answer.declined || answer.topic !== "security") return [];
  const ids = new Set<string>();
  if (AREA[answer.area]) ids.add(answer.area);
  if (/^To defend against|\nHow to defend against it:/m.test(answer.answer)) ids.add("skandamata");
  if (/\nWhat it is: |^\*\*|^Most likely first:/m.test(answer.answer)) ids.add("brahmacharini");
  return [...ids].filter((id) => SPECIALISTS.some((s) => s.id === id));
}

/** Streams an answer in word by word, as it would be read, then shows its sources once the words are in.
 *  Off for history and for anyone who asked for reduced motion. */
function useStream(text: string, on: boolean): { shown: string; done: boolean } {
  const sources = text.match(/\n*Sources?: .*$/)?.[0] ?? "";
  const body = sources ? text.slice(0, text.length - sources.length) : text;
  const words = useMemo(() => body.split(/(\s+)/), [body]);
  const [count, setCount] = useState(on ? 0 : words.length);
  useEffect(() => {
    if (!on || document.hidden || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setCount(words.length);
      return;
    }
    // Paced by the clock, not by ticks: a browser that throttles timers still finishes on time.
    const started = Date.now();
    const duration = Math.min(1800, 400 + words.length * 6);
    const timer = setInterval(() => {
      const n = Math.ceil(((Date.now() - started) / duration) * words.length);
      setCount(n);
      if (n >= words.length) clearInterval(timer);
    }, 24);
    return () => clearInterval(timer);
  }, [on, words]);
  const done = count >= words.length;
  return { shown: done ? text : words.slice(0, count).join(""), done };
}

function SatiMark() {
  return (
    <span
      aria-hidden="true"
      className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(135deg,rgb(var(--astra)),rgb(var(--astra)/0.55))] text-xs font-bold text-white shadow-[0_0_0_3px_rgb(var(--astra)/0.15)]"
    >
      S
    </span>
  );
}

/** A general answer, laid out like a conversation: Sati's mark, the models it drew on, the answer streamed
 *  in, then what to do with it and what to ask next. Labelled as general knowledge, not a finding. */
function GeneralTurn({
  answer,
  onAsk,
  stream = false,
}: {
  answer: GeneralAnswer;
  onAsk?: (question: string) => void;
  stream?: boolean;
}) {
  const { shown, done } = useStream(answer.answer, stream);
  const used = consulted(answer);
  const next = done && !answer.declined ? followUps(answer.answer) : [];
  return (
    <div data-turn="general" className="flex gap-3">
      <SatiMark />
      <div className="min-w-0 flex-1 space-y-3">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 pt-1 text-xs">
          <span className="font-semibold text-[rgb(var(--ink))]">Sati</span>
          {used.length > 0 && (
            <span className="inline-flex flex-wrap items-center gap-1.5 text-[rgb(var(--faint))]" title={`Served by ${servedName(answer.model)}`}>
              · drew on
              {used.map((id) => {
                const s = specialist(id);
                return (
                  <span key={id} style={hueOf(s)} className="sp-tint inline-flex items-center gap-1 rounded-full py-0.5 pl-0.5 pr-2 font-medium">
                    <Monogram s={s} size="xs" />
                    {s.name}
                  </span>
                );
              })}
            </span>
          )}
        </p>
        <div data-answer className={answer.declined ? "rounded-xl border border-dashed border-[rgb(var(--edge))] px-4 py-3" : ""}>
          <AnswerText text={shown} muted={answer.declined} still={stream} />
          {!done && <span aria-hidden="true" className="ml-0.5 inline-block h-4 w-2 animate-pulse rounded-sm bg-[rgb(var(--astra))] align-middle" />}
        </div>
        {done && (
          <div className="rise flex flex-wrap items-center gap-x-3 gap-y-2">
            <AnswerActions text={answer.answer} />
            <span className="text-[11px] text-[rgb(var(--faint))]">General knowledge from MITRE ATT&amp;CK, CAPEC and CISA, not your systems</span>
          </div>
        )}
        {next.length > 0 && onAsk && (
          <div className="rise flex flex-col items-start gap-1.5 pt-1">
            {next.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onAsk(q)}
                className="focusable group inline-flex max-w-full items-center gap-2 rounded-xl border border-[rgb(var(--edge))] px-3 py-1.5 text-left text-sm text-[rgb(var(--muted))] transition hover:border-[rgb(var(--astra))]/50 hover:bg-[rgb(var(--astra))]/5 hover:text-[rgb(var(--ink))]"
              >
                <span aria-hidden="true" className="text-[rgb(var(--astra))] transition group-hover:translate-x-0.5">↳</span>
                <span className="min-w-0">{q}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** A data-reading model's verdict on a held-out example. */
/** Sets the specialist's accent for the .sp-* classes. */
function hueOf(s: Specialist): CSSProperties {
  return hue(s.id === "auto" ? "sati" : s.id) as CSSProperties;
}

const MONO = {
  xs: "h-5 w-5 rounded-full text-[10px]",
  sm: "h-6 w-6 rounded-full text-[11px]",
  md: "h-9 w-9 rounded-xl text-sm",
  lg: "h-9 w-9 rounded-xl text-sm ring-4 ring-[rgb(var(--sp)/0.25)]",
};

/** A specialist's monogram in its own colour, so nine names read apart at a glance. */
function Monogram({ s, size }: { s: Specialist; size: keyof typeof MONO }) {
  return (
    <span aria-hidden="true" style={hueOf(s)} className={`sp-solid inline-flex shrink-0 items-center justify-center font-semibold ${MONO[size]}`}>
      {s.name[0]}
    </span>
  );
}

function SpecialistTurn({ form, text, verdict }: { form: string; text: string; verdict?: Verdict }) {
  const s = specialist(form);
  return (
    <div data-turn="specialist" style={hueOf(s)} className="max-w-[95%] space-y-2">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <Monogram s={s} size="sm" />
        <span className="sp-text font-semibold">{s.name}</span>
        <span className="text-[rgb(var(--muted))]">· {s.job.toLowerCase()}</span>
      </p>
      <div className="rounded-2xl border border-[rgb(var(--edge))] border-l-[3px] border-l-[rgb(var(--sp))] bg-[rgb(var(--panel))] px-4 py-3.5">
        {verdict && <VerdictView v={verdict} />}
        <AnswerText text={text} />
        <p className="mt-3 border-t border-[rgb(var(--edge))] pt-2 text-[11px] text-[rgb(var(--faint))]">
          Run live on an example it never trained on, with the truth beside the answer.
        </p>
      </div>
    </div>
  );
}

/** A specialist's run as a picture: right or wrong, then its score, ranking or timeline. */
function VerdictView({ v }: { v: Verdict }) {
  const tone = v.correct === null ? "--muted" : v.correct ? "--ok" : "--crit";
  return (
    <div className="rise mb-3.5 space-y-3">
      <span
        className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
        style={{ background: `rgb(var(${tone}) / 0.14)`, color: `rgb(var(${tone}))` }}
      >
        <span aria-hidden="true">{v.correct === null ? "?" : v.correct ? "✓" : "✗"}</span>
        {v.correct === null ? "Left to a person" : v.correct ? "Right" : "Wrong"}
      </span>
      {v.gauge && <Gauge {...v.gauge} />}
      {v.ranking && <Ranking rows={v.ranking} />}
      {v.timeline && <Timeline {...v.timeline} />}
    </div>
  );
}

/** Score against threshold on one line. Past the threshold is the flagged side, shaded. */
function Gauge({ score, threshold, flagged, high, low }: NonNullable<Verdict["gauge"]>) {
  // Probabilities crowd at the ends (a score of 1.000 against 0.9997), so they are drawn on log-odds,
  // where that gap is visible. Other scores are drawn around the threshold.
  const unit = score >= 0 && score <= 1 && threshold >= 0 && threshold <= 1;
  const odds = (x: number) => {
    const p = Math.min(Math.max(x, 1e-6), 1 - 1e-6);
    return Math.log(p / (1 - p));
  };
  const span = Math.max(Math.abs(score - threshold) * 1.6, 1e-6);
  const place = (x: number) => (unit ? (odds(x) + 14) / 28 : (x - threshold + span) / (2 * span));
  const at = (x: number) => `${Math.min(100, Math.max(0, place(x) * 100))}%`;
  return (
    <div>
      <div className="relative h-3 overflow-hidden rounded-full bg-[rgb(var(--raised))]">
        <div className="absolute inset-y-0 right-0 bg-[rgb(var(--crit))]/20" style={{ left: at(threshold) }} />
        <div className="absolute inset-y-0 w-0.5 bg-[rgb(var(--ink))]/60" style={{ left: at(threshold) }} />
        <div
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[rgb(var(--panel))] shadow"
          style={{ left: at(score), background: flagged ? "rgb(var(--crit))" : "rgb(var(--ok))" }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-[rgb(var(--faint))]">
        <span>{low}</span>
        <span className="tnum">
          score {score.toFixed(4)} · threshold {threshold.toFixed(4)}
        </span>
        <span>{high}</span>
      </div>
    </div>
  );
}

/** Katyayani's top five, longest bar first; the true root cause is marked. */
function Ranking({ rows }: { rows: NonNullable<Verdict["ranking"]> }) {
  const top = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-6);
  return (
    <ol className="space-y-1.5 text-xs">
      {rows.map((r, i) => (
        <li key={r.label} className="grid grid-cols-[1.25rem_minmax(0,9rem)_1fr_auto] items-center gap-2">
          <span className="tnum text-[rgb(var(--faint))]">{i + 1}</span>
          <span className={`mono truncate ${r.truth ? "font-semibold text-[rgb(var(--ok))]" : ""}`}>{r.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-[rgb(var(--raised))]">
            <span
              className="block h-full rounded-full"
              style={{ width: `${(Math.abs(r.value) / top) * 100}%`, background: r.truth ? "rgb(var(--ok))" : "rgb(var(--sp) / 0.6)" }}
            />
          </span>
          <span className="tnum text-[rgb(var(--muted))]">
            {r.value.toFixed(1)}σ{r.truth ? " · root" : ""}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** The incident minute by minute: its window shaded, Siddhidatri's flags as ticks, and where Shailaputri caught it and Mahagauri called it over. */
function Timeline({ minutes, start, end, flags, caught, declared }: NonNullable<Verdict["timeline"]>) {
  const at = (m: number) => `${(m / Math.max(minutes, 1)) * 100}%`;
  return (
    <div>
      <div className="relative h-8 overflow-hidden rounded-lg bg-[rgb(var(--raised))]">
        <div className="absolute inset-y-0 bg-[rgb(var(--warn))]/20" style={{ left: at(start), width: at(end - start) }} />
        {flags.map((f, i) =>
          f ? <span key={i} className="absolute bottom-0 h-2.5 w-px bg-[rgb(var(--sp))]" style={{ left: at(i) }} /> : null,
        )}
        {caught !== null && (
          <span className="absolute inset-y-0 w-0.5 bg-[rgb(var(--ok))]" style={{ left: at(caught) }} title={`Shailaputri caught it at minute ${caught}`} />
        )}
        {declared !== null && (
          <span className="absolute inset-y-0 w-0.5 bg-[rgb(var(--ink))]" style={{ left: at(declared) }} title={`Mahagauri called it over at minute ${declared}`} />
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[rgb(var(--faint))]">
        <span className="inline-flex items-center gap-1"><span className="h-2 w-3 rounded-sm bg-[rgb(var(--warn))]/40" />incident</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-px bg-[rgb(var(--sp))]" />Siddhidatri flag</span>
        {caught !== null && <span className="inline-flex items-center gap-1"><span className="h-2.5 w-0.5 bg-[rgb(var(--ok))]" />Shailaputri caught it</span>}
        {declared !== null && <span className="inline-flex items-center gap-1"><span className="h-2.5 w-0.5 bg-[rgb(var(--ink))]" />Mahagauri: over</span>}
        <span className="tnum ml-auto">{minutes} min</span>
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
  const [rated, setRated] = useState<"up" | "down" | null>(null);
  const rate = (r: "up" | "down") => {
    setRated(r);
    try {
      const kept = JSON.parse(localStorage.getItem("pashu.ask.rated") ?? "{}") as Record<string, string>;
      kept[text.slice(0, 120)] = r;
      localStorage.setItem("pashu.ask.rated", JSON.stringify(kept));
    } catch {
      // Not remembered.
    }
  };
  const icon = "focusable inline-flex h-8 w-8 items-center justify-center rounded-lg text-[rgb(var(--faint))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]";
  return (
    <span className="-ml-1.5 flex items-center gap-0.5">
      <button type="button" onClick={copy} className={icon} aria-label={copied ? "Copied" : "Copy answer"} title={copied ? "Copied" : "Copy"}>
        {copied ? (
          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 text-[rgb(var(--ok))]" fill="none" stroke="currentColor" strokeWidth={2.2}><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
        ) : (
          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" strokeLinecap="round" /></svg>
        )}
      </button>
      <button type="button" onClick={share} className={icon} aria-label="Share answer" title="Share">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8}><path d="M12 15V3m0 0L8 7m4-4 4 4M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      <button type="button" onClick={() => rate("up")} aria-pressed={rated === "up"} className={`${icon} ${rated === "up" ? "text-[rgb(var(--ok))]" : ""}`} aria-label="Helpful" title="Helpful">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill={rated === "up" ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.8}><path d="M7 10v11H4V10h3Zm0 0 4-7a2 2 0 0 1 2 2v4h5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 16.8 21H7" strokeLinejoin="round" /></svg>
      </button>
      <button type="button" onClick={() => rate("down")} aria-pressed={rated === "down"} className={`${icon} ${rated === "down" ? "text-[rgb(var(--crit))]" : ""}`} aria-label="Not helpful" title="Not helpful">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 rotate-180" fill={rated === "down" ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.8}><path d="M7 10v11H4V10h3Zm0 0 4-7a2 2 0 0 1 2 2v4h5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 16.8 21H7" strokeLinejoin="round" /></svg>
      </button>
    </span>
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
  modelIds = [],
}: {
  modelIds?: string[];
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

  const chosen = served(specialist(special), modelIds);
  return (
    <div className="space-y-6 py-2">
      <div className="relative isolate overflow-hidden rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-5 py-7 sm:px-8">
        <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-10" />
        <div aria-hidden="true" className="mb-4 flex -space-x-1.5">
          {SPECIALISTS.slice(1).map((s) => (
            <span key={s.id} className="rounded-full ring-2 ring-[rgb(var(--panel))]">
              <Monogram s={s} size="sm" />
            </span>
          ))}
        </div>
        <p className="label text-[rgb(var(--astra))]">Sati AI</p>
        <Greeting />
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          Sati, the investigation agent, runs on nine models built and trained in this project. Ask a question, or pick a
          specialist and run it on real data it never trained on — every answer shows the truth beside it, and none uses an
          outside AI.
        </p>
      </div>

      <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        {SPECIALISTS.map((x) => served(x, modelIds)).map((s) => {
          const active = s.id === chosen.id;
          const tag = s.kind === "auto" || s.kind === "ask" ? "Q&A" : s.kind === "private" ? "private" : "live data";
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSpecialist?.(s.id)}
                aria-pressed={active}
                style={hueOf(s)}
                className={`focusable lift flex h-full w-full flex-col rounded-2xl border p-3.5 text-left transition ${
                  active ? "sp-card" : "sp-hover border-[rgb(var(--edge))] bg-[rgb(var(--panel))]"
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <Monogram s={s} size={active ? "lg" : "md"} />
                  <span
                    title={s.kind === "private" ? "Not served publicly" : "Live"}
                    className={`h-2 w-2 rounded-full ${s.kind === "private" ? "bg-[rgb(var(--faint))]" : "bg-[rgb(var(--ok))] shadow-[0_0_0_3px_rgb(var(--ok)/0.2)]"}`}
                  />
                </span>
                <span className="mt-2.5 text-sm font-semibold">{s.name}</span>
                <span className="mt-0.5 text-xs leading-snug text-[rgb(var(--muted))]">{s.job}</span>
                <span className="flex-1" />
                <span className="sp-tint mt-2.5 self-start whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">{tag}</span>
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
                    style={hueOf(chosen)}
                    className="focusable lift sp-hover group flex items-center gap-3 rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-3 py-2.5 text-left transition disabled:opacity-50"
                  >
                    <span aria-hidden="true" className="sp-tint inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[10px] transition group-hover:scale-110">
                      ▶
                    </span>
                    <span className="min-w-0">
                      <span className="mono block truncate text-sm text-[rgb(var(--ink))]">{e.id}</span>
                      <span className="block truncate text-xs text-[rgb(var(--faint))]">{e.label}</span>
                    </span>
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

/** "Good evening, Ana": the time of day, and the name when signed in. Set after mount, so the server
 *  and the browser render the same first frame. */
function Greeting() {
  const { me } = useAccount();
  const [part, setPart] = useState<string | null>(null);
  useEffect(() => {
    const h = new Date().getHours();
    setPart(h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening");
  }, []);
  const name = me && me.user.provider !== "guest" ? me.user.name.split(" ")[0] : null;
  return (
    <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
      {part ? `${part}${name ? `, ${name}` : ""}.` : "Sati AI."}{" "}
      <span className="text-[rgb(var(--muted))]">What are we investigating?</span>
    </h1>
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
          className="focusable lift group flex items-start gap-3 rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-4 py-3.5 text-left transition hover:border-[rgb(var(--astra))]/50 disabled:opacity-50"
        >
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium text-[rgb(var(--ink))]">{s.q}</span>
            <span className="mt-0.5 block text-xs text-[rgb(var(--faint))]">{s.hint}</span>
          </span>
          <span aria-hidden="true" className="mt-0.5 text-[rgb(var(--faint))] transition group-hover:translate-x-0.5 group-hover:text-[rgb(var(--astra))]">
            →
          </span>
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

const STEPS_GENERAL = [
  "Reading the question",
  "Searching MITRE ATT&CK, CAPEC and CISA's catalogue",
  "Picking the models that fit",
  "Ranking and writing the answer",
];
const STEPS_INCIDENT = ["Reading the question", "Gathering this incident's evidence", "Checking each claim against it", "Writing the answer"];

/** While Sati works: the steps its pipeline takes, each ticked as time passes, so the wait reads as work. */
function Waiting({ model, general }: { model?: string; general: boolean }) {
  const [ms, setMs] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const tick = setInterval(() => setMs(Date.now() - started), 200);
    return () => clearInterval(tick);
  }, []);
  const steps = general ? STEPS_GENERAL : STEPS_INCIDENT;
  const at = Math.min(steps.length - 1, Math.floor(ms / 650));
  return (
    <div data-waiting aria-live="polite" className="flex gap-3">
      <span className="relative inline-flex h-7 w-7 shrink-0">
        <span className="absolute inset-0 animate-ping rounded-full bg-[rgb(var(--astra))]/30" />
        <SatiMark />
      </span>
      <div className="min-w-0 space-y-1.5 pt-1">
        <p className="flex items-center gap-2 text-xs">
          <span className="font-semibold">Sati</span>
          <span className="text-[rgb(var(--faint))]">is working{model ? ` · ${model}` : ""}</span>
          {ms >= 2000 && <span className="tnum text-[rgb(var(--faint))]">{Math.floor(ms / 1000)}s</span>}
        </p>
        <ol className="space-y-1 text-sm">
          {steps.slice(0, at + 1).map((step, i) => (
            <li key={step} className="rise flex items-center gap-2">
              {i < at ? (
                <span aria-hidden="true" className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-[rgb(var(--ok))]/15 text-[10px] text-[rgb(var(--ok))]">✓</span>
              ) : (
                <span aria-hidden="true" className="inline-flex h-4 w-4 items-center justify-center">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-[rgb(var(--astra))] border-t-transparent" />
                </span>
              )}
              <span className={i < at ? "text-[rgb(var(--faint))]" : "text-[rgb(var(--ink))]"}>{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
