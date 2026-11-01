"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  MATCH_PAIRS,
  PASSWORD_DUELS,
  PHISH_OR_LEGIT,
  URL_DETECTIVE,
  shuffled,
  type PhishRound,
} from "@/lib/games";

/**
 * Games for learning security by playing: quick rounds, an explanation after
 * every answer, and a best score kept in this browser.
 *
 * Phish or legit (spot the scam), URL detective (find the real domain),
 * Password duel (pick the stronger) and Match up (pair terms with meanings).
 * Content is in lib/games.ts; nothing typed here leaves the page.
 */
const BEST_KEY = "pashu.games.best";

type GameId = "phish" | "url" | "password" | "match";

const GAMES: { id: GameId; title: string; blurb: string; level: string; icon: string; hue: string }[] = [
  { id: "phish", title: "Phish or legit?", blurb: "Ten messages. Call each one.", level: "Beginner", icon: "✉", hue: "236 72 153" },
  { id: "url", title: "URL detective", blurb: "Where does the link really go?", level: "Beginner", icon: "⌕", hue: "14 165 233" },
  { id: "password", title: "Password duel", blurb: "Pick the stronger of two.", level: "Beginner", icon: "⚿", hue: "245 158 11" },
  { id: "match", title: "Match up", blurb: "Pair each term with its meaning.", level: "Beginner", icon: "◇", hue: "139 92 246" },
];

function readBest(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(BEST_KEY) ?? "{}") as Record<string, number>;
  } catch {
    return {};
  }
}

function saveBest(id: GameId, score: number): void {
  try {
    const best = readBest();
    if (score > (best[id] ?? -1)) localStorage.setItem(BEST_KEY, JSON.stringify({ ...best, [id]: score }));
  } catch {
    // Not remembered; the game still works.
  }
}

export function Games() {
  const [open, setOpen] = useState<GameId>("phish");
  const [best, setBest] = useState<Record<string, number>>({});
  const [round, setRound] = useState(0);
  useEffect(() => setBest(readBest()), []);
  const finished = (id: GameId, score: number) => {
    saveBest(id, score);
    setBest(readBest());
  };
  const restart = () => setRound((r) => r + 1);

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Games" className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        {GAMES.map((g) => (
          <button
            key={g.id}
            type="button"
            role="tab"
            aria-selected={open === g.id}
            onClick={() => setOpen(g.id)}
            style={{ ["--sp" as string]: g.hue }}
            className={`focusable lift flex items-start gap-3 rounded-2xl border p-3.5 text-left transition ${
              open === g.id ? "sp-card" : "sp-hover border-[rgb(var(--edge))] bg-[rgb(var(--panel))]"
            }`}
          >
            <span aria-hidden="true" className="sp-solid inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg">
              {g.icon}
            </span>
            <span className="min-w-0">
              <span className="block font-semibold leading-tight">{g.title}</span>
              <span className="mt-0.5 block text-xs text-[rgb(var(--muted))]">{g.blurb}</span>
              <span className="tnum sp-text mt-1 block text-[11px] font-medium">
                {best[g.id] !== undefined ? `Best: ${best[g.id]}` : "Not played yet"}
              </span>
            </span>
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        key={`${open}-${round}`}
        className="rise rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 sm:p-6"
      >
        {open === "phish" && <PhishGame seed={round + 1} onDone={(s) => finished("phish", s)} onAgain={restart} />}
        {open === "url" && <UrlGame seed={round + 1} onDone={(s) => finished("url", s)} onAgain={restart} />}
        {open === "password" && <PasswordGame seed={round + 1} onDone={(s) => finished("password", s)} onAgain={restart} />}
        {open === "match" && <MatchGame seed={round + 7} onDone={(s) => finished("match", s)} onAgain={restart} />}
      </div>
    </div>
  );
}

/** The bar across the top of a game: where you are, the score and the streak. */
function Progress({ at, of, score, streak }: { at: number; of: number; score: number; streak?: number }) {
  return (
    <div className="mb-4 space-y-2">
      <div className="flex items-center gap-3 text-xs text-[rgb(var(--muted))]">
        <span className="tnum">
          {Math.min(at + 1, of)} of {of}
        </span>
        <span className="tnum ml-auto font-semibold text-[rgb(var(--ink))]">Score {score}</span>
        {streak !== undefined && streak > 1 && (
          <span className="tnum rounded-full bg-[rgb(var(--warn))]/15 px-2 py-0.5 font-semibold text-[rgb(var(--warn))]">
            {streak} in a row
          </span>
        )}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[rgb(var(--raised))]" aria-hidden="true">
        <div className="h-full rounded-full bg-[rgb(var(--astra))] transition-[width] duration-500" style={{ width: `${(at / of) * 100}%` }} />
      </div>
    </div>
  );
}

function Feedback({ right, children }: { right: boolean; children: ReactNode }) {
  return (
    <div
      role="status"
      className={`rise mt-4 rounded-xl border p-3.5 text-sm leading-relaxed ${
        right ? "border-[rgb(var(--ok))]/40 bg-[rgb(var(--ok))]/10" : "border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10"
      }`}
    >
      <p className="font-semibold" style={{ color: `rgb(var(${right ? "--ok" : "--crit"}))` }}>
        {right ? "✓ Right" : "✗ Not quite"}
      </p>
      <p className="mt-1 text-[rgb(var(--ink))]">{children}</p>
    </div>
  );
}

function Finish({ score, of, onAgain, lines }: { score: number; of: number; onAgain: () => void; lines: [number, string][] }) {
  const share = score / of;
  const verdict = lines.find(([min]) => share >= min)?.[1] ?? "";
  return (
    <div className="rise py-6 text-center">
      <p className="text-5xl" aria-hidden="true">
        {share === 1 ? "🏆" : share >= 0.7 ? "🎯" : "📚"}
      </p>
      <p className="tnum mt-3 text-3xl font-semibold">
        {score} / {of}
      </p>
      <p className="mx-auto mt-2 max-w-md text-sm text-[rgb(var(--muted))]">{verdict}</p>
      <button
        type="button"
        onClick={onAgain}
        className="focusable mt-5 rounded-xl bg-[rgb(var(--astra))] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110"
      >
        Play again
      </button>
    </div>
  );
}

const VERDICTS: [number, string][] = [
  [1, "Perfect. You would catch these at work."],
  [0.7, "Strong. Read the explanations for the ones you missed: they are the tricks that work on real people."],
  [0, "Worth another round: each explanation names the clue to look for next time."],
];

type GameProps = { seed: number; onDone: (score: number) => void; onAgain: () => void };

function useRounds(total: number, onDone: (score: number) => void) {
  const [at, setAt] = useState(0);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [picked, setPicked] = useState<boolean | null>(null);
  const answer = (right: boolean) => {
    if (picked !== null) return;
    setPicked(right);
    setScore((s) => s + (right ? 1 : 0));
    setStreak((s) => (right ? s + 1 : 0));
  };
  const next = () => {
    if (at + 1 >= total) onDone(score);
    setAt((a) => a + 1);
    setPicked(null);
  };
  return { at, score, streak, picked, answer, next, done: at >= total };
}

function NextButton({ onClick, last }: { onClick: () => void; last: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      autoFocus
      className="focusable mt-3 rounded-xl bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110"
    >
      {last ? "See your score" : "Next →"}
    </button>
  );
}

function Message({ m }: { m: PhishRound }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))]">
      <div className="flex items-center gap-2 border-b border-[rgb(var(--edge))] px-4 py-2 text-xs text-[rgb(var(--faint))]">
        <span className="rounded-full bg-[rgb(var(--raised))] px-2 py-0.5 font-medium text-[rgb(var(--muted))]">{m.channel}</span>
        <span className="mono truncate">{m.from}</span>
      </div>
      <div className="px-4 py-3.5">
        {m.subject && <p className="font-semibold">{m.subject}</p>}
        <p className={`text-sm leading-relaxed ${m.subject ? "mt-1.5" : ""}`}>{m.body}</p>
      </div>
    </div>
  );
}

function PhishGame({ seed, onDone, onAgain }: GameProps) {
  const rounds = useMemo(() => shuffled(PHISH_OR_LEGIT, seed), [seed]);
  const g = useRounds(rounds.length, onDone);
  if (g.done) return <Finish score={g.score} of={rounds.length} onAgain={onAgain} lines={VERDICTS} />;
  const m = rounds[g.at];
  return (
    <div>
      <Progress at={g.at} of={rounds.length} score={g.score} streak={g.streak} />
      <Message m={m} />
      {g.picked === null ? (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => g.answer(m.phish)}
            className="focusable rounded-xl border-2 border-[rgb(var(--crit))]/50 bg-[rgb(var(--crit))]/10 px-4 py-3 font-semibold text-[rgb(var(--crit))] transition hover:bg-[rgb(var(--crit))]/20"
          >
            🎣 Phish
          </button>
          <button
            type="button"
            onClick={() => g.answer(!m.phish)}
            className="focusable rounded-xl border-2 border-[rgb(var(--ok))]/50 bg-[rgb(var(--ok))]/10 px-4 py-3 font-semibold text-[rgb(var(--ok))] transition hover:bg-[rgb(var(--ok))]/20"
          >
            ✓ Legit
          </button>
        </div>
      ) : (
        <>
          <Feedback right={g.picked}>
            <strong>{m.phish ? "Phish." : "Legit."}</strong> {m.why}
          </Feedback>
          <NextButton onClick={g.next} last={g.at + 1 >= rounds.length} />
        </>
      )}
    </div>
  );
}

function Choices({
  options,
  answer,
  chosen,
  onPick,
  mono = false,
}: {
  options: string[];
  answer: number;
  chosen: number | null;
  onPick: (i: number) => void;
  mono?: boolean;
}) {
  return (
    <div className="mt-4 grid gap-2">
      {options.map((o, i) => {
        const state = chosen === null ? "" : i === answer ? "right" : i === chosen ? "wrong" : "dim";
        return (
          <button
            key={o}
            type="button"
            disabled={chosen !== null}
            onClick={() => onPick(i)}
            className={`focusable rounded-xl border px-4 py-3 text-left text-sm transition ${mono ? "mono" : ""} ${
              state === "right"
                ? "border-[rgb(var(--ok))] bg-[rgb(var(--ok))]/10"
                : state === "wrong"
                  ? "border-[rgb(var(--crit))] bg-[rgb(var(--crit))]/10"
                  : state === "dim"
                    ? "border-[rgb(var(--edge))] opacity-50"
                    : "border-[rgb(var(--edge-strong))] hover:border-[rgb(var(--astra))]/60 hover:bg-[rgb(var(--raised))]"
            }`}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}

function UrlGame({ seed, onDone, onAgain }: GameProps) {
  const rounds = useMemo(() => shuffled(URL_DETECTIVE, seed), [seed]);
  const g = useRounds(rounds.length, onDone);
  const [chosen, setChosen] = useState<number | null>(null);
  if (g.done) return <Finish score={g.score} of={rounds.length} onAgain={onAgain} lines={VERDICTS} />;
  const r = rounds[g.at];
  return (
    <div>
      <Progress at={g.at} of={rounds.length} score={g.score} streak={g.streak} />
      <p className="text-sm text-[rgb(var(--muted))]">Where does this link really take you?</p>
      <p className="mono mt-2 break-all rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-4 py-3 text-sm">
        {r.url}
      </p>
      <Choices
        options={r.options}
        answer={r.answer}
        chosen={chosen}
        mono
        onPick={(i) => {
          setChosen(i);
          g.answer(i === r.answer);
        }}
      />
      {g.picked !== null && (
        <>
          <Feedback right={g.picked}>{r.why}</Feedback>
          <NextButton
            onClick={() => {
              setChosen(null);
              g.next();
            }}
            last={g.at + 1 >= rounds.length}
          />
        </>
      )}
    </div>
  );
}

function PasswordGame({ seed, onDone, onAgain }: GameProps) {
  const rounds = useMemo(() => shuffled(PASSWORD_DUELS, seed), [seed]);
  const g = useRounds(rounds.length, onDone);
  const [chosen, setChosen] = useState<"a" | "b" | null>(null);
  if (g.done) return <Finish score={g.score} of={rounds.length} onAgain={onAgain} lines={VERDICTS} />;
  const d = rounds[g.at];
  return (
    <div>
      <Progress at={g.at} of={rounds.length} score={g.score} streak={g.streak} />
      <p className="text-sm text-[rgb(var(--muted))]">Which is stronger?</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-stretch">
        {(["a", "b"] as const).map((side, i) => {
          const text = d[side];
          const state = chosen === null ? "" : side === d.stronger ? "right" : side === chosen ? "wrong" : "dim";
          return (
            <div key={side} className="contents">
              {i === 1 && (
                <span className="hidden items-center justify-center text-sm font-semibold text-[rgb(var(--faint))] sm:flex" aria-hidden="true">
                  vs
                </span>
              )}
              <button
                type="button"
                disabled={chosen !== null}
                onClick={() => {
                  setChosen(side);
                  g.answer(side === d.stronger);
                }}
                className={`focusable lift rounded-2xl border-2 p-5 text-center transition ${
                  state === "right"
                    ? "border-[rgb(var(--ok))] bg-[rgb(var(--ok))]/10"
                    : state === "wrong"
                      ? "border-[rgb(var(--crit))] bg-[rgb(var(--crit))]/10"
                      : state === "dim"
                        ? "border-[rgb(var(--edge))] opacity-50"
                        : "border-[rgb(var(--edge-strong))] hover:border-[rgb(var(--warn))]/60"
                }`}
              >
                <span className={`block break-words ${text.includes(" ") && text.length > 26 ? "text-sm" : "mono text-lg"}`}>{text}</span>
              </button>
            </div>
          );
        })}
      </div>
      {g.picked !== null && (
        <>
          <Feedback right={g.picked}>{d.why}</Feedback>
          <NextButton
            onClick={() => {
              setChosen(null);
              g.next();
            }}
            last={g.at + 1 >= rounds.length}
          />
        </>
      )}
    </div>
  );
}

/** Match up: six pairs face down; turn two at a time. Score is two per pair, less a point for every two misses. */
function MatchGame({ seed, onDone, onAgain }: GameProps) {
  const cards = useMemo(() => {
    const pairs = shuffled(MATCH_PAIRS, seed).slice(0, 6);
    return shuffled(
      pairs.flatMap((p, i) => [
        { key: `t${i}`, pair: i, text: p.term, term: true },
        { key: `m${i}`, pair: i, text: p.meaning, term: false },
      ]),
      seed * 31,
    );
  }, [seed]);
  const [up, setUp] = useState<number[]>([]);
  const [matched, setMatched] = useState<Set<number>>(new Set());
  const [misses, setMisses] = useState(0);
  const [reported, setReported] = useState(false);
  const done = matched.size === 6;
  const score = Math.max(0, 6 * 2 - Math.floor(misses / 2));

  useEffect(() => {
    if (up.length !== 2) return;
    const [a, b] = up;
    if (cards[a].pair === cards[b].pair) {
      setMatched((m) => new Set(m).add(cards[a].pair));
      setUp([]);
      return;
    }
    const t = setTimeout(() => {
      setMisses((x) => x + 1);
      setUp([]);
    }, 900);
    return () => clearTimeout(t);
  }, [up, cards]);

  useEffect(() => {
    if (done && !reported) {
      onDone(score);
      setReported(true);
    }
  }, [done, reported, score, onDone]);

  if (done) {
    return (
      <Finish
        score={score}
        of={12}
        onAgain={onAgain}
        lines={[
          [1, "Every pair, no wasted turns."],
          [0.7, "All matched. Fewer misses next time for a perfect score."],
          [0, "All matched. The terms will stick faster on a second round."],
        ]}
      />
    );
  }
  return (
    <div>
      <div className="mb-4 flex items-center gap-3 text-xs text-[rgb(var(--muted))]">
        <span className="tnum">{matched.size} of 6 pairs</span>
        <span className="tnum ml-auto">misses {misses}</span>
      </div>
      <p className="mb-3 text-sm text-[rgb(var(--muted))]">Turn two cards: a term and the meaning that goes with it.</p>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        {cards.map((c, i) => {
          const shown = up.includes(i) || matched.has(c.pair);
          return (
            <button
              key={c.key}
              type="button"
              disabled={shown || up.length === 2}
              onClick={() => setUp((u) => [...u, i])}
              aria-label={shown ? c.text : "Face-down card"}
              className={`focusable flex min-h-[5.5rem] items-center justify-center rounded-xl border p-2 text-center text-xs leading-snug transition sm:text-sm ${
                matched.has(c.pair)
                  ? "border-[rgb(var(--ok))]/50 bg-[rgb(var(--ok))]/10 text-[rgb(var(--ink))]"
                  : shown
                    ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))]/10"
                    : "border-[rgb(var(--edge-strong))] bg-[rgb(var(--raised))] hover:border-[rgb(var(--astra))]/50"
              } ${c.term && shown ? "font-semibold" : ""}`}
            >
              {shown ? c.text : <span aria-hidden="true" className="text-xl text-[rgb(var(--faint))]">?</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
