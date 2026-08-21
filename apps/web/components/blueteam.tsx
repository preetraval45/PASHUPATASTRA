"use client";

/**
 * Blue team mode, played.
 *
 * The console shows a finished investigation. This shows one alert and asks the
 * player to do the rest, which is the only arrangement in which the reasoning
 * is visible — a chain presented after the fact always looks obvious.
 *
 * The answer is never in this component's props. It arrives from the server in
 * the response to the attempt and nowhere earlier, so reading the page source
 * gets you the same thing reading the screen does.
 */

import Link from "next/link";
import { useCallback, useState } from "react";

import {
  getBriefing,
  investigateEntity,
  submitAttempt,
  type Briefing,
  type Investigation,
  type Verdict2,
} from "@/lib/api";
import { Ago, Badge, Empty, Ident, Panel, statusForSeverity } from "@/components/ui";

type Stage = "briefing" | "marked";

const GRADE: Record<Verdict2["grade"], { label: string; status: "critical" | "high" | "warning" | "ok" }> = {
  clean: { label: "clean", status: "ok" },
  sound: { label: "sound", status: "warning" },
  shaky: { label: "shaky", status: "high" },
  missed: { label: "missed", status: "critical" },
};

export function BlueTeam({ briefing: initial }: { briefing: Briefing }) {
  const [briefing, setBriefing] = useState(initial);
  const [stage, setStage] = useState<Stage>("briefing");

  const [opened, setOpened] = useState<Record<string, Investigation>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState<string | null>(null);
  const [action, setAction] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict2 | null>(null);
  const [error, setError] = useState<string | null>(null);

  const investigate = useCallback(
    async (key: string) => {
      if (opened[key] || busy) return;
      setBusy(key);
      const result = await investigateEntity(briefing.incident_id, key);
      if (result) setOpened((prior) => ({ ...prior, [key]: result }));
      else setError("Could not reach the API.");
      setBusy(null);
    },
    [briefing.incident_id, busy, opened],
  );

  const submit = useCallback(async () => {
    if (!diagnosis || !action) return;
    setBusy("submit");
    setError(null);
    const result = await submitAttempt(briefing.incident_id, {
      diagnosis_id: diagnosis,
      action_id: action,
      // What was actually opened, not what was offered. The server takes this
      // on trust; a player who lies has awarded themselves points in a training
      // exercise, and the alternative is session state for a game with no
      // stakes.
      investigated: Object.keys(opened),
    });
    if (result) {
      setVerdict(result);
      setStage("marked");
    } else {
      setError("Could not submit the attempt.");
    }
    setBusy(null);
  }, [action, briefing.incident_id, diagnosis, opened]);

  const retry = useCallback(async () => {
    setBusy("reset");
    const fresh = await getBriefing(briefing.incident_id);
    if (fresh) setBriefing(fresh);
    setOpened({});
    setDiagnosis(null);
    setAction(null);
    setVerdict(null);
    setError(null);
    setStage("briefing");
    setBusy(null);
  }, [briefing.incident_id]);

  if (stage === "marked" && verdict) {
    return <Marked verdict={verdict} onRetry={retry} busy={busy === "reset"} />;
  }

  const ready = Boolean(diagnosis && action);

  return (
    <>
      <Panel title="The alert" aside="this is all you get to start with">
        {briefing.alert ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <Badge status={statusForSeverity(briefing.alert.severity)}>
                {briefing.alert.severity ?? "unrated"}
              </Badge>
              <Ident>{briefing.alert.entity_key}</Ident>
              <span className="text-xs text-[rgb(var(--faint))]">
                <Ago at={briefing.alert.at} />
              </span>
            </div>
            <p className="text-sm leading-relaxed">{briefing.alert.summary}</p>
          </div>
        ) : (
          <Empty art="ledger" title="This scenario has no opening signal." />
        )}
      </Panel>

      <Panel
        title="Investigate"
        aside={`${Object.keys(opened).length} of ${briefing.entities.length} opened`}
      >
        <p className="mb-3 text-sm text-[rgb(var(--muted))]">
          Open what you would look at. One of the explanations below is
          plausible and wrong, and something here rules it out.
        </p>
        <div className="space-y-2">
          {briefing.entities.map((key) => (
            <Entity
              key={key}
              entityKey={key}
              result={opened[key]}
              busy={busy === key}
              onOpen={() => investigate(key)}
            />
          ))}
        </div>
      </Panel>

      <Panel title="What happened?" aside={`${briefing.scoring.diagnosis} points`}>
        <div className="space-y-2">
          {briefing.candidates.map((candidate) => (
            <Choice
              key={candidate.id}
              name="diagnosis"
              checked={diagnosis === candidate.id}
              onSelect={() => setDiagnosis(candidate.id)}
              label={candidate.statement}
            />
          ))}
        </div>
      </Panel>

      <Panel
        title="What would you do about it?"
        aside={`${briefing.scoring.response} points`}
      >
        <p className="mb-3 text-sm text-[rgb(var(--muted))]">
          Proportionality is scored. Doing too little and doing too much are
          both wrong, and one of these would do far too much.
        </p>
        <div className="space-y-2">
          {briefing.actions.map((option) => (
            <Choice
              key={option.id}
              name="action"
              checked={action === option.id}
              onSelect={() => setAction(option.id)}
              label={option.description}
              meta={
                <span className="flex items-center gap-2">
                  <Ident>{option.id}</Ident>
                  <span className="text-[rgb(var(--faint))]">
                    risk {option.base_risk}
                  </span>
                  {option.read_only && (
                    <span className="text-[rgb(var(--faint))]">changes nothing</span>
                  )}
                </span>
              }
            />
          ))}
        </div>
      </Panel>

      {error && (
        <p className="text-sm text-[rgb(var(--warn))]">{error}</p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={!ready || busy === "submit"}
          className="focusable rounded border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))] disabled:opacity-40"
        >
          {busy === "submit" ? "Marking…" : "Commit to this answer"}
        </button>
        {!ready && (
          <span className="text-xs text-[rgb(var(--faint))]">
            Choose an explanation and a response first.
          </span>
        )}
      </div>
    </>
  );
}

function Entity({
  entityKey,
  result,
  busy,
  onOpen,
}: {
  entityKey: string;
  result?: Investigation;
  busy: boolean;
  onOpen: () => void;
}) {
  if (!result) {
    return (
      <button
        type="button"
        onClick={onOpen}
        disabled={busy}
        className="focusable flex w-full items-center gap-3 rounded border border-[rgb(var(--edge))] px-3 py-2.5 text-left text-sm transition hover:bg-[rgb(var(--raised))] disabled:opacity-50"
      >
        <span aria-hidden="true" className="text-[rgb(var(--faint))]">
          +
        </span>
        <Ident>{entityKey}</Ident>
        <span className="ml-auto text-xs text-[rgb(var(--faint))]">
          {busy ? "opening…" : "look at this"}
        </span>
      </button>
    );
  }

  return (
    <div className="rounded border border-[rgb(var(--edge-strong))] bg-[rgb(var(--raised))] px-3 py-2.5">
      <p className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <Ident>{entityKey}</Ident>
        <span className="text-xs text-[rgb(var(--faint))]">
          {result.events.length} {result.events.length === 1 ? "event" : "events"}
        </span>
      </p>
      {result.events.length === 0 ? (
        <p className="text-xs text-[rgb(var(--faint))]">
          Nothing recorded against this one.
        </p>
      ) : (
        <ol className="space-y-1.5">
          {result.events.map((event) => (
            <li key={event.id} className="flex flex-wrap items-baseline gap-x-2 text-xs">
              <span className="text-[rgb(var(--faint))]">
                <Ago at={event.at} />
              </span>
              <Badge status={statusForSeverity(event.severity)}>
                {event.severity ?? "info"}
              </Badge>
              <span className="min-w-0 flex-1 text-[rgb(var(--muted))]">
                {event.summary || event.detection}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Choice({
  name,
  checked,
  onSelect,
  label,
  meta,
}: {
  name: string;
  checked: boolean;
  onSelect: () => void;
  label: string;
  meta?: React.ReactNode;
}) {
  return (
    <label
      className={`flex cursor-pointer gap-3 rounded border px-3 py-2.5 text-sm transition ${
        checked
          ? "border-[rgb(var(--astra))]/50 bg-[rgb(var(--raised))]"
          : "border-[rgb(var(--edge))] hover:bg-[rgb(var(--raised))]"
      }`}
    >
      {/* A real radio, not a styled div. Arrow keys move between options and a
          screen reader announces the group, both of which a div reimplements
          badly or not at all. */}
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onSelect}
        className="focusable mt-1 accent-[rgb(var(--astra))]"
      />
      <span className="min-w-0 flex-1 space-y-1">
        <span className="block leading-snug">{label}</span>
        {meta && <span className="block text-xs">{meta}</span>}
      </span>
    </label>
  );
}

function Marked({
  verdict,
  onRetry,
  busy,
}: {
  verdict: Verdict2;
  onRetry: () => void;
  busy: boolean;
}) {
  const grade = GRADE[verdict.grade];
  const { answer } = verdict;

  return (
    <>
      <Panel title="Marked" aside={`${verdict.total} / 100`}>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Badge status={grade.status}>{grade.label}</Badge>
          <span className="text-2xl font-semibold tabular-nums">{verdict.total}</span>
          <span className="text-sm text-[rgb(var(--faint))]">out of 100</span>
        </div>
        <dl className="space-y-3">
          {verdict.breakdown.map((part) => (
            <div key={part.name} className="flex flex-wrap gap-x-3 gap-y-1">
              <dt className="w-28 shrink-0 text-sm">{part.name}</dt>
              <dd className="mono w-16 shrink-0 text-sm tabular-nums text-[rgb(var(--muted))]">
                {part.points}/{part.of}
              </dd>
              <dd className="min-w-0 flex-1 text-sm text-[rgb(var(--muted))]">
                {part.note}
              </dd>
            </div>
          ))}
        </dl>
      </Panel>

      <Panel title="What actually happened">
        <p className="mb-4 text-sm leading-relaxed">{answer.diagnosis}</p>
        <ol className="space-y-3">
          {answer.chain.map((step, index) => (
            <li key={index} className="border-l-2 border-[rgb(var(--edge-strong))] pl-3">
              <p className="text-sm">
                <Ident>{step.entity_key}</Ident>{" "}
                <span className="text-[rgb(var(--muted))]">{step.transition}</span>
              </p>
              {step.technique && (
                <p className="mono mt-1 text-[11px] text-[rgb(var(--faint))]">
                  <a
                    href={step.technique.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                  >
                    {step.technique.id}
                  </a>{" "}
                  {step.technique.name} · {step.technique.tactic}
                </p>
              )}
            </li>
          ))}
        </ol>
      </Panel>

      {/* The part worth having. Being told the right answer teaches less than
          being shown the specific observation that killed the answer you were
          drawn to. */}
      {answer.decoy && (
        <Panel title="The plausible wrong answer" aside="and what ruled it out">
          <p className="mb-3 text-sm italic text-[rgb(var(--muted))]">
            &ldquo;{answer.decoy.statement}&rdquo;
          </p>
          <ul className="space-y-2">
            {answer.decoy.ruled_out_by.map((row) => (
              <li key={row.id} className="text-sm">
                <span className="text-[rgb(var(--muted))]">{row.summary}</span>{" "}
                <Link
                  href={`/evidence/${encodeURIComponent(row.id)}`}
                  className="focusable mono rounded text-[11px] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                >
                  {row.id}
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onRetry}
          disabled={busy}
          className="focusable rounded border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))] disabled:opacity-40"
        >
          Try this one again
        </button>
        <Link
          href="/blue-team"
          className="focusable rounded border border-[rgb(var(--edge))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]"
        >
          Another scenario
        </Link>
      </div>
    </>
  );
}
