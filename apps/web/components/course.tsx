"use client";

/**
 * The course's interactive parts: the quiz at the end of each module, and the
 * evaluation that summarises what this browser has learned.
 *
 * Progress lives in `localStorage` and nowhere else — like the drill token,
 * a learner's record is theirs, stays on their device, and can be erased with
 * one click.
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui";
import { arranged, levelReached, MODULES, PASS_MARK, type Question } from "@/lib/training";

const KEY = "pashu.training.v1";

export type Record_ = { best: number; last: number; attempts: number; passed: boolean; at: string };
type Store = Record<string, Record_>;

function read(): Store {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Store;
  } catch {
    return {};
  }
}

function write(store: Store) {
  try {
    localStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    // Not remembered; the quiz still works.
  }
}

export function useCourse() {
  const [store, setStore] = useState<Store>({});
  useEffect(() => setStore(read()), []);
  const record = useCallback((slug: string, score: number) => {
    const prior = read();
    const before = prior[slug];
    const next: Store = {
      ...prior,
      [slug]: {
        best: Math.max(score, before?.best ?? 0),
        last: score,
        attempts: (before?.attempts ?? 0) + 1,
        passed: (before?.passed ?? false) || score >= PASS_MARK,
        at: new Date().toISOString(),
      },
    };
    write(next);
    setStore(next);
  }, []);
  const reset = useCallback(() => {
    write({});
    setStore({});
  }, []);
  return { store, record, reset };
}

/** The test at the end of a module: answer everything, submit, then every
 *  question shows whether you were right and why. */
export function Quiz({ slug, questions: written }: { slug: string; questions: Question[] }) {
  const { store, record } = useCourse();
  // Options in a stable shuffled order, so the right answer is not always in one place (lib/training.ts).
  const questions = useMemo(() => written.map(arranged), [written]);
  const [answers, setAnswers] = useState<(number | null)[]>(() => questions.map(() => null));
  const [submitted, setSubmitted] = useState(false);

  const correct = answers.filter((a, i) => a === questions[i].answer).length;
  const score = correct / questions.length;
  const complete = answers.every((a) => a !== null);
  const prior = store[slug];

  const submit = () => {
    setSubmitted(true);
    record(slug, score);
  };

  const retry = () => {
    setAnswers(questions.map(() => null));
    setSubmitted(false);
  };

  return (
    <div data-quiz={slug} className="space-y-5">
      {prior && !submitted && (
        <p className="text-sm text-[rgb(var(--muted))]">
          Your best so far: <strong className="text-[rgb(var(--ink))]">{Math.round(prior.best * 100)}%</strong> over{" "}
          {prior.attempts} attempt{prior.attempts === 1 ? "" : "s"}
          {prior.passed ? " — passed." : `. Pass mark is ${PASS_MARK * 100}%.`}
        </p>
      )}

      <ol className="space-y-4">
        {questions.map((question, qi) => {
          const chosen = answers[qi];
          return (
            <li key={qi} className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
              <p className="font-medium">
                <span className="tnum mr-2 text-[rgb(var(--faint))]">{qi + 1}.</span>
                {question.q}
              </p>
              <div role="radiogroup" aria-label={`Question ${qi + 1}`} className="mt-3 grid gap-2 sm:grid-cols-2">
                {question.options.map((option, oi) => {
                  const picked = chosen === oi;
                  const isAnswer = oi === question.answer;
                  const tone = !submitted
                    ? picked
                      ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))]/10"
                      : "border-[rgb(var(--edge))] hover:bg-[rgb(var(--raised))]"
                    : isAnswer
                      ? "border-[rgb(var(--ok))]/60 bg-[rgb(var(--ok))]/10"
                      : picked
                        ? "border-[rgb(var(--crit))]/60 bg-[rgb(var(--crit))]/10"
                        : "border-[rgb(var(--edge))] opacity-60";
                  return (
                    <button
                      key={oi}
                      type="button"
                      role="radio"
                      aria-checked={picked}
                      disabled={submitted}
                      onClick={() => setAnswers((prev) => prev.map((a, i) => (i === qi ? oi : a)))}
                      className={`focusable rounded-lg border px-3 py-2 text-left text-sm transition ${tone}`}
                    >
                      {submitted && isAnswer && <span aria-hidden="true" className="mr-1.5 text-[rgb(var(--ok))]">✓</span>}
                      {submitted && picked && !isAnswer && <span aria-hidden="true" className="mr-1.5 text-[rgb(var(--crit))]">✗</span>}
                      {option}
                    </button>
                  );
                })}
              </div>
              {submitted && (
                <p className={`mt-3 text-sm leading-relaxed ${chosen === question.answer ? "text-[rgb(var(--muted))]" : "text-[rgb(var(--ink))]"}`}>
                  <strong>{chosen === question.answer ? "Correct. " : "Not quite. "}</strong>
                  {question.why}
                </p>
              )}
            </li>
          );
        })}
      </ol>

      {submitted ? (
        <div
          data-result
          className={`flex flex-wrap items-center gap-3 rounded-xl border p-4 ${
            score >= PASS_MARK ? "border-[rgb(var(--ok))]/50 bg-[rgb(var(--ok))]/5" : "border-[rgb(var(--warn))]/50 bg-[rgb(var(--warn))]/5"
          }`}
        >
          <p className="text-lg font-semibold">
            {correct}/{questions.length} · {Math.round(score * 100)}%
          </p>
          <Badge status={score >= PASS_MARK ? "ok" : "warning"}>{score >= PASS_MARK ? "passed" : "not yet"}</Badge>
          <p className="text-sm text-[rgb(var(--muted))]">
            {score >= PASS_MARK ? "This module is complete." : `Pass mark is ${PASS_MARK * 100}%. Re-read the lesson and try again.`}
          </p>
          <button
            type="button"
            onClick={retry}
            className="focusable ml-auto rounded-md border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm transition hover:bg-[rgb(var(--raised))]"
          >
            Try again
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={!complete}
          onClick={submit}
          className="focusable rounded-lg bg-[rgb(var(--astra))] px-5 py-2.5 text-sm font-medium text-[rgb(var(--ground))] transition hover:brightness-110 disabled:bg-[rgb(var(--raised))] disabled:text-[rgb(var(--faint))]"
        >
          {complete ? "Submit answers" : `Answer all ${questions.length} questions to submit`}
        </button>
      )}
    </div>
  );
}

/** The learner's evaluation: every module, its best score, and the overall. */
export function Evaluation() {
  const { store, reset } = useCourse();
  const passed = MODULES.filter((m) => store[m.slug]?.passed).length;
  const attempted = MODULES.filter((m) => store[m.slug]);
  const average = attempted.length
    ? attempted.reduce((sum, m) => sum + store[m.slug].best, 0) / attempted.length
    : null;
  const share = Math.round((passed / MODULES.length) * 100);
  const level = levelReached((slug) => Boolean(store[slug]?.passed));
  const reached = MODULES.find((m) => m.level === level);

  return (
    <div data-evaluation className="space-y-5">
      <div data-level={level} className="rounded-xl border border-[rgb(var(--astra))]/40 bg-[rgb(var(--astra))]/5 p-4">
        <p className="label">Your awareness level</p>
        <p className="mt-1 text-2xl font-semibold">
          {level === 0 ? "Not started" : `Level ${level} · ${reached?.form}`}
        </p>
        <ol className="mt-3 flex gap-1" aria-label="Nine levels">
          {MODULES.map((m) => (
            <li
              key={m.slug}
              title={`Level ${m.level} · ${m.form} — ${m.title}`}
              className={`h-2 flex-1 rounded-full ${
                store[m.slug]?.passed
                  ? m.level <= level
                    ? "bg-[rgb(var(--astra))]"
                    : "bg-[rgb(var(--astra))]/40"
                  : "bg-[rgb(var(--raised))]"
              }`}
            />
          ))}
        </ol>
        {level < MODULES.length ? (
          <Link
            href={`/training/${MODULES[level].slug}`}
            className="focusable mt-3 inline-flex items-center gap-2 rounded-lg bg-[rgb(var(--astra))] px-3.5 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          >
            {level === 0 ? "Start level 1" : `Continue: level ${level + 1}`} — {MODULES[level].title} →
          </Link>
        ) : (
          <p className="mt-2 text-sm font-medium text-[rgb(var(--astra))]">All nine levels passed.</p>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
          <p className="label">Modules passed</p>
          <p className="tnum mt-1 text-2xl font-semibold">
            {passed}/{MODULES.length}
          </p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[rgb(var(--raised))]" aria-hidden="true">
            <div className="h-full rounded-full bg-[rgb(var(--astra))] transition-all duration-700" style={{ width: `${share}%` }} />
          </div>
        </div>
        <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
          <p className="label">Average best score</p>
          <p className="tnum mt-1 text-2xl font-semibold">{average === null ? "—" : `${Math.round(average * 100)}%`}</p>
          <p className="mt-0.5 text-xs text-[rgb(var(--faint))]">across modules attempted</p>
        </div>
        <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
          <p className="label">Status</p>
          <p className="mt-1 text-2xl font-semibold">
            {passed === MODULES.length ? "All nine passed" : passed > 0 ? "In progress" : "Not started"}
          </p>
          <p className="mt-0.5 text-xs text-[rgb(var(--faint))]">pass mark {PASS_MARK * 100}% per module</p>
        </div>
      </div>

      <ul className="space-y-2">
        {MODULES.map((m) => {
          const r = store[m.slug];
          return (
            <li key={m.slug} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              {/* Full width on a phone, a fixed column from sm up, so the bar is never squeezed to nothing. */}
              <Link href={`/training/${m.slug}`} className="focusable w-full truncate rounded hover:text-[rgb(var(--astra))] sm:w-64 sm:shrink-0">
                <span className="tnum text-[rgb(var(--faint))]">{m.level}.</span> {m.title}
              </Link>
              <div className="h-2 min-w-[4rem] flex-1 overflow-hidden rounded-full bg-[rgb(var(--raised))]" aria-hidden="true">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${(r?.best ?? 0) * 100}%`,
                    background: r?.passed ? "rgb(var(--ok))" : "rgb(var(--warn))",
                  }}
                />
              </div>
              <span className="tnum w-12 text-right text-xs">{r ? `${Math.round(r.best * 100)}%` : "—"}</span>
              <span className="w-20 text-right">
                {r ? <Badge status={r.passed ? "ok" : "warning"}>{r.passed ? "passed" : "retry"}</Badge> : <span className="text-xs text-[rgb(var(--faint))]">not taken</span>}
              </span>
            </li>
          );
        })}
      </ul>

      {attempted.length > 0 && (
        <button
          type="button"
          onClick={reset}
          className="focusable rounded text-xs text-[rgb(var(--faint))] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
        >
          Erase my course record from this browser
        </button>
      )}
    </div>
  );
}

/** A module's status chip on the course grid. */
export function ModuleStatus({ slug }: { slug: string }) {
  const { store } = useCourse();
  const r = store[slug];
  const level = levelReached((s) => Boolean(store[s]?.passed));
  const next = MODULES[level]?.slug === slug;
  if (!r && next)
    return (
      <span className="rounded-full bg-[rgb(var(--astra))] px-2 py-0.5 text-[11px] font-semibold text-white">
        Up next
      </span>
    );
  if (!r) return <span className="text-xs text-[rgb(var(--astra))]">Start →</span>;
  return <Badge status={r.passed ? "ok" : "warning"}>{r.passed ? `passed · ${Math.round(r.best * 100)}%` : `best ${Math.round(r.best * 100)}%`}</Badge>;
}
