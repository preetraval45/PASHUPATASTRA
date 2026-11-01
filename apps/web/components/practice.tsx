"use client";

import { useEffect, useMemo, useState } from "react";

import { AnswerText } from "@/components/answertext";
import { CARDS, TIERS, type Tier } from "@/lib/questionbank";

/**
 * Practice questions, beginner to expert, as flashcards: think of your answer,
 * reveal the worked one, and say whether you knew it. Cards you knew are kept
 * in this browser and leave the deck; the rest come round again.
 */
const KEY = "pashu.practice.known";

function readKnown(): string[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

export function Practice() {
  const [tier, setTier] = useState<Tier>("beginner");
  const [known, setKnown] = useState<string[]>([]);
  const [at, setAt] = useState(0);
  const [shown, setShown] = useState(false);
  useEffect(() => setKnown(readKnown()), []);

  const all = useMemo(() => CARDS.filter((c) => c.tier === tier), [tier]);
  const deck = all.filter((c) => !known.includes(c.q));
  const card = deck.length ? deck[at % deck.length] : null;

  const mark = (knew: boolean) => {
    if (!card) return;
    if (knew) {
      const next = [...known, card.q];
      setKnown(next);
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        // Not remembered.
      }
    } else {
      setAt((a) => a + 1);
    }
    setShown(false);
  };
  const reset = () => {
    const next = known.filter((q) => !all.some((c) => c.q === q));
    setKnown(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Not remembered.
    }
    setAt(0);
  };

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Level" className="no-scrollbar fade-x -mx-1 flex gap-2 overflow-x-auto px-1">
        {TIERS.map((t) => {
          const count = CARDS.filter((c) => c.tier === t.id).length;
          const done = CARDS.filter((c) => c.tier === t.id && known.includes(c.q)).length;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tier === t.id}
              onClick={() => {
                setTier(t.id);
                setAt(0);
                setShown(false);
              }}
              className={`focusable shrink-0 rounded-xl border px-3.5 py-2 text-left transition ${
                tier === t.id
                  ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))]/10"
                  : "border-[rgb(var(--edge))] bg-[rgb(var(--panel))] hover:border-[rgb(var(--astra))]/50"
              }`}
            >
              <span className="block text-sm font-semibold">{t.label}</span>
              <span className="tnum block text-[11px] text-[rgb(var(--faint))]">
                {done} of {count} known
              </span>
            </button>
          );
        })}
      </div>

      <div className="rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 sm:p-6">
        <p className="text-xs text-[rgb(var(--faint))]">{TIERS.find((t) => t.id === tier)?.who}</p>
        {card ? (
          <div key={card.q} className="rise">
            <p className="tnum mt-1 text-xs text-[rgb(var(--muted))]">{deck.length} left in this level</p>
            <p className="mt-3 text-lg font-semibold leading-snug">{card.q}</p>
            {shown ? (
              <>
                <div className="mt-4 rounded-xl border border-[rgb(var(--astra))]/30 bg-[rgb(var(--astra))]/5 p-4">
                  <AnswerText text={card.a} muted />
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => mark(true)}
                    className="focusable rounded-xl bg-[rgb(var(--ok))] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110"
                  >
                    I knew it
                  </button>
                  <button
                    type="button"
                    onClick={() => mark(false)}
                    className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm font-medium transition hover:bg-[rgb(var(--raised))]"
                  >
                    Show it again later
                  </button>
                </div>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setShown(true)}
                className="focusable mt-4 rounded-xl bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110"
              >
                Think of your answer, then reveal
              </button>
            )}
          </div>
        ) : (
          <div className="rise py-4 text-center">
            <p className="text-4xl" aria-hidden="true">
              🎓
            </p>
            <p className="mt-2 font-semibold">You know every {tier} question.</p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {tier !== "expert" && (
                <button
                  type="button"
                  onClick={() => {
                    setTier(TIERS[TIERS.findIndex((t) => t.id === tier) + 1].id);
                    setAt(0);
                  }}
                  className="focusable rounded-xl bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white"
                >
                  Next level →
                </button>
              )}
              <button
                type="button"
                onClick={reset}
                className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm"
              >
                Practise this level again
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
