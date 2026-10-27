"use client";

import { useEffect, useState } from "react";

import { getTreeExamples, runTreeExample, type TreeExamples, type TreeForm, type TreeRun } from "@/lib/api";

const COPY: Record<TreeForm, { name: string; item: string; flagged: string; clear: string; action: string }> = {
  kalaratri: {
    name: "Kalaratri",
    item: "log session",
    flagged: "anomalous",
    clear: "normal",
    action: "Check the session",
  },
  chandraghanta: {
    name: "Chandraghanta",
    item: "network flow",
    flagged: "an attack",
    clear: "benign",
    action: "Check the flow",
  },
};

/**
 * Run Kalaratri or Chandraghanta on a held-out example from its test split.
 *
 * The API scores the example on each request with the served model, and the
 * truth is shown beside the answer, including when the model is wrong. Both
 * models were trained on research-use-only data, so the licence is shown too.
 */
export function TryTree({ form }: { form: TreeForm }) {
  const copy = COPY[form];
  const [data, setData] = useState<TreeExamples | null | undefined>(undefined);
  const [picked, setPicked] = useState<string>("");
  const [result, setResult] = useState<TreeRun | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getTreeExamples(form).then((d) => {
      setData(d);
      if (d?.examples.length) setPicked(d.examples[0].id);
    });
  }, [form]);

  async function run(id: string) {
    setBusy(true);
    setResult(await runTreeExample(form, id));
    setBusy(false);
  }

  if (data === undefined) return <p className="text-sm text-[rgb(var(--faint))]">Loading the examples…</p>;
  if (data === null || data.examples.length === 0)
    return (
      <p className="text-sm text-[rgb(var(--faint))]">
        The live model is not reachable right now. Its measured results are below.
      </p>
    );

  return (
    <div className="space-y-4" data-try={form}>
      <p className="text-sm text-[rgb(var(--muted))]">
        Pick a {copy.item} from the test split{data.dataset ? ` of ${data.dataset}` : ""}, which {copy.name} never
        trained on. The API scores it live, and the true label is shown beside the answer.
        {data.operating_point && <> The threshold is set for {data.operating_point}.</>}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`${form}-example`} className="sr-only">Example</label>
        <select
          id={`${form}-example`}
          value={picked}
          onChange={(e) => setPicked(e.target.value)}
          className="focusable max-w-full rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-3 py-2 text-sm"
        >
          {data.examples.map((e) => (
            <option key={e.id} value={e.id}>
              {e.id}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => run(picked)}
          disabled={busy || !picked}
          className="focusable rounded-lg bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Scoring…" : copy.action}
        </button>
      </div>
      {result && (
        <div aria-live="polite" className="space-y-2">
          <p className={`text-sm font-medium ${result.correct ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
            <span aria-hidden="true">{result.correct ? "✓ " : "✗ "}</span>
            {result.correct ? "Right" : "Wrong"}: {copy.name} called it {result.flagged ? copy.flagged : copy.clear}, and
            it is {result.truth ? copy.flagged : copy.clear} ({result.label}).
          </p>
          <p className="tnum text-xs text-[rgb(var(--faint))]">
            Score {result.score.toFixed(4)} against threshold {result.threshold.toFixed(4)}
          </p>
        </div>
      )}
      {data.licence && <p className="text-xs text-[rgb(var(--faint))]">{data.licence}</p>}
    </div>
  );
}
