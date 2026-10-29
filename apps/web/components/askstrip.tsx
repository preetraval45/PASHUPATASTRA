"use client";

import Link from "next/link";
import { useState } from "react";

import { AnswerText } from "@/components/answertext";
import { askGeneral, type GeneralAnswer } from "@/lib/api";

/**
 * Sati, the investigation agent, answering on the home page — one tap, no typing.
 *
 * Each chip is a real question to the live API, answered by the project's own
 * models (the same path as /ask). The chips are ones those models answer well
 * today, checked against the served models on 28–29 Oct; nothing here is a
 * canned reply. A link continues the conversation in Sati AI.
 */
const QUESTIONS = [
  {
    label: "An attacker dumps LSASS memory",
    q: "Which ATT&CK technique is it when an attacker dumps LSASS memory to get passwords?",
  },
  {
    label: "Ransomware is encrypting file shares",
    q: "How do we defend against ransomware encrypting our file shares?",
  },
  {
    label: "Malware runs at every logon",
    q: "Which ATT&CK technique is it when an attacker schedules a task to run their malware at every logon?",
  },
  { label: "What is Log4Shell?", q: "What should we do about Log4Shell (CVE-2021-44228)?" },
];

type State =
  | { kind: "idle" }
  | { kind: "busy"; q: string }
  | { kind: "done"; q: string; answer: GeneralAnswer }
  | { kind: "error"; q: string; message: string };

export function AskStrip() {
  const [state, setState] = useState<State>({ kind: "idle" });

  async function ask(q: string) {
    setState({ kind: "busy", q });
    const result = await askGeneral(q, []);
    setState("answer" in result ? { kind: "done", q, answer: result.answer } : { kind: "error", q, message: result.error });
  }

  const asked = state.kind === "idle" ? null : state.q;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {QUESTIONS.map((item) => {
          const active = asked === item.q;
          return (
            <button
              key={item.q}
              type="button"
              onClick={() => ask(item.q)}
              disabled={state.kind === "busy"}
              aria-pressed={active}
              className={`focusable rounded-full border px-4 py-2 text-sm transition disabled:opacity-60 ${
                active
                  ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))]/10 text-[rgb(var(--ink))]"
                  : "border-[rgb(var(--edge-strong))] text-[rgb(var(--muted))] hover:border-[rgb(var(--astra))]/60 hover:text-[rgb(var(--ink))]"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div aria-live="polite" className="min-h-[3rem]">
        {state.kind === "idle" && (
          <p className="text-sm text-[rgb(var(--faint))]">Tap one. The answer comes live from Sati&apos;s own models, with its sources.</p>
        )}
        {state.kind === "busy" && (
          <div className="space-y-2" role="status" aria-label="Sati is answering">
            <div className="h-3 w-2/3 animate-pulse rounded bg-[rgb(var(--raised))]" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-[rgb(var(--raised))]" />
            <div className="h-3 w-3/5 animate-pulse rounded bg-[rgb(var(--raised))]" />
          </div>
        )}
        {state.kind === "error" && <p className="text-sm text-[rgb(var(--warn))]">{state.message}</p>}
        {state.kind === "done" && (
          <div className="rise rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
            <AnswerText text={state.answer.answer} />
            <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[rgb(var(--edge))] pt-3 text-xs">
              <span className="text-[rgb(var(--faint))]">Answered live · no external AI</span>
              <Link href="/ask" className="focusable rounded font-medium text-[rgb(var(--astra))] hover:underline">
                Keep asking in Sati AI →
              </Link>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
