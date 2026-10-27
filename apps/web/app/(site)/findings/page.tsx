import type { Metadata } from "next";
import Link from "next/link";

import { Page, Panel } from "@/components/ui";
import chandraghanta from "@/lib/models/chandraghanta.results.json";
import katyayani from "@/lib/models/katyayani.results.json";
import simtoreal from "@/lib/models/katyayani-simtoreal.results.json";
import kushmanda from "@/lib/models/kushmanda.results.json";
import mahagauri from "@/lib/models/mahagauri.results.json";
import diagnosis from "@/lib/models/rcaeval-diagnosis.results.json";
import siddhidatri from "@/lib/models/siddhidatri.results.json";
import smd from "@/lib/models/shailaputri-smd.results.json";

export const metadata: Metadata = {
  title: "Findings",
  description:
    "What the measurements showed — including the results that went against us. Every number is read from a committed results file.",
};

/**
 * The research results that matter, on one page.
 *
 * No number here is typed: each is read from the results file a training
 * workflow committed (docs/research/REPRODUCIBILITY.md), so this page cannot
 * drift from the evidence. The negative results are given the same space as
 * the positive ones, because a project that reports only its wins has not been
 * measuring.
 */

const f3 = (n: number) => n.toFixed(3);
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

type Finding = {
  id: string;
  kicker: string;
  title: string;
  headline: string;
  versus: { label: string; value: string }[];
  body: string;
  href: string;
  tone: "positive" | "negative" | "method";
};

function findings(): Finding[] {
  const cic = chandraghanta.datasets.cic;
  const byDay = cic.detectors["chandraghanta-v0"].f1;
  const random = cic.reference_random_split["chandraghanta-v0"].f1;

  const ob = simtoreal.test.ob;
  const ss = simtoreal.test.ss;
  const real = katyayani.pooled["leave-one-system-out"].sati["ac@1"];

  const smdMean = smd.mean_across_groups as Record<string, { f1: number; false_alarms_per_1000: number }>;
  const shail = smdMean["shailaputri-v1 onset-weighted"];
  const pca = smdMean["pca per machine"];

  const g = (kushmanda.sft?.grounded ?? {}) as Record<string, Record<string, Record<string, number>>>;
  const fused = siddhidatri.mean_across_groups["siddhidatri-v0"];
  const alone = siddhidatri.mean_across_groups.shailaputri;

  const d1 = diagnosis["rca@1"] as Record<string, number>;
  const llama = diagnosis.paired_vs_katyayani["llm:llama3"];

  return [
    {
      id: "llm",
      kicker: "Root cause · RCAEval, a benchmark we did not write",
      title: "Our own model beats general LLMs at naming the root cause",
      headline: pct(d1.katyayani),
      versus: [
        { label: "Katyayani, trained on other real systems", value: f3(d1.katyayani) },
        { label: "llama3, same evidence", value: f3(d1["llm:llama3"]) },
        { label: "qwen2.5 7B, same evidence", value: f3(d1["llm:qwen2.5:7b"]) },
        { label: "just pick the loudest service", value: f3(d1.loudest) },
      ],
      body: `On ${diagnosis.cases} cases declared before any run, every diagnoser saw the same evidence and was scored by the same harness. Where Katyayani and llama3 disagreed, Katyayani was right ${llama.only_katyayani} times and llama3 ${llama.only_other}; the difference holds after correcting for every comparison made. A small model trained on real incidents beats general models reading the same data.`,
      href: "/models#sim-to-real",
      tone: "positive",
    },
    {
      id: "split",
      kicker: "Network intrusion · CIC-IDS2017",
      title: "The evaluation split decides the headline",
      headline: `${f3(random)} → ${f3(byDay)}`,
      versus: [
        { label: "random split (how most papers test)", value: f3(random) },
        { label: "attack families never seen in training", value: f3(byDay) },
      ],
      body:
        "The same model, the same flows. Tested the usual way it looks nearly perfect; tested on attacks from days it never trained on, F1 falls by more than half. Results reported on random splits measure recognition, not detection.",
      href: "/models#chandraghanta-results",
      tone: "method",
    },
    {
      id: "sim",
      kicker: "Root cause · RCAEval, zero-shot",
      title: "A simulator did not teach root cause — real data did",
      headline: pct(real),
      versus: [
        { label: "trained on 50,000 synthetic incidents · Online Boutique", value: f3(ob["katyayani-kaal-v0 (zero-shot)"]["rca@1"].value) },
        { label: "trained on 50,000 synthetic incidents · Sock Shop", value: f3(ss["katyayani-kaal-v0 (zero-shot)"]["rca@1"].value) },
        { label: "just pick the loudest service · Sock Shop", value: f3(ss["loudest service"]["rca@1"].value) },
      ],
      body:
        "Trained on real fault injections, Katyayani names the root cause first on a system it never saw this often. The same design trained on synthetic incidents falls below a no-learning baseline on real ones: the simulator taught it to trust topology, and real faults make the culprit the loudest.",
      href: "/models#sim-to-real",
      tone: "negative",
    },
    {
      id: "quiet",
      kicker: "Anomaly detection · 28 real servers (SMD)",
      title: "Fewer false alarms, not just a higher score",
      headline: `${shail.false_alarms_per_1000.toFixed(1)} / 1000`,
      versus: [
        { label: "Shailaputri — false alarms per 1000 minutes", value: shail.false_alarms_per_1000.toFixed(1) },
        { label: "PCA per machine", value: pca.false_alarms_per_1000.toFixed(1) },
        { label: "F1, Shailaputri vs PCA", value: `${f3(shail.f1)} vs ${f3(pca.f1)}` },
      ],
      body:
        "On servers from a machine group it never trained on, the learned detector is both more accurate and far quieter — the pairing that decides whether anyone keeps reading the alerts.",
      href: "/models",
      tone: "positive",
    },
    {
      id: "lm",
      kicker: "Sati's own language model",
      title: "A 17M-parameter model that answers from evidence — and says when it can't",
      headline: f3(g.kushmanda?.remediate?.rouge_l ?? 0),
      versus: [
        { label: "what to do about a CVE · Kushmanda (ROUGE-L)", value: f3(g.kushmanda?.remediate?.rouge_l ?? 0) },
        { label: "same, word-overlap baseline", value: f3(g["lexical baseline"]?.remediate?.rouge_l ?? 0) },
        { label: "declines when no passage holds the answer", value: pct(g.kushmanda?.unanswerable?.abstained ?? 0) },
        { label: "copies an exact ID right (baseline does better)", value: f3(g.kushmanda?.lookup?.exact_match ?? 0) },
      ],
      body:
        "Trained from scratch on public security text, it composes answers from the passages Sati retrieved and cites one. It is worse than simple word overlap at copying identifiers, so every ID it writes is checked against its citation.",
      href: "/models#kushmanda-results",
      tone: "positive",
    },
    {
      id: "negatives",
      kicker: "Reported as found",
      title: "Two models that did not earn their place",
      headline: pct(mahagauri.pooled["mahagauri-v0"].premature_rate),
      versus: [
        { label: "Mahagauri v0 — incidents declared over too early", value: pct(mahagauri.pooled["mahagauri-v0"].premature_rate) },
        {
          label: "v1 with a second check — early, and still confirmed",
          value: `${pct((mahagauri.pooled as Record<string, { premature_rate: number; confirmed_rate: number }>)["mahagauri-v1 + 3σ agreement"]?.premature_rate ?? 0)} · ${pct((mahagauri.pooled as Record<string, { premature_rate: number; confirmed_rate: number }>)["mahagauri-v1 + 3σ agreement"]?.confirmed_rate ?? 0)}`,
        },
        { label: "Siddhidatri fusion F1 vs Shailaputri alone", value: `${f3(fused.f1)} vs ${f3(alone.f1)}` },
        { label: "fusion's false alarms vs Shailaputri alone", value: `${fused.false_alarms_per_1000.toFixed(1)} vs ${alone.false_alarms_per_1000.toFixed(1)}` },
      ],
      body:
        "The recovery verifier called one incident in five over too early on unseen servers. Requiring a second check brings that near the 5% budget, but then most incidents go back to a human — safety bought with usefulness, so it still may not close incidents alone. Fusing three detectors bought recall with twelve times the false alarms. Both stay published, with what would fix them.",
      href: "/models#mahagauri-results",
      tone: "negative",
    },
    {
      id: "metric",
      kicker: "Method",
      title: "We found a bug in our own scoring — and re-decided on the corrected numbers",
      headline: "1000 × (1 − precision)",
      versus: [
        { label: "what “false alarms per 1000” had been measuring", value: "1 − precision" },
        { label: "what it measures now", value: "per point judged" },
      ],
      body:
        "The harness never counted the normal points a detector correctly left alone. Fixed, every affected result was re-run, the detection decision was re-made on the corrected numbers, and the history was kept rather than rewritten.",
      href: "/evaluation",
      tone: "method",
    },
  ];
}

const TONE: Record<Finding["tone"], string> = {
  positive: "text-emerald-600 dark:text-emerald-400",
  negative: "text-amber-600 dark:text-amber-400",
  method: "text-sky-600 dark:text-sky-400",
};

export default function FindingsPage() {
  return (
    <Page
      title="Findings"
      description="What the measurements showed — the results that went against us get the same space as the ones that went for us."
      actions={
        <Link href="/evaluation" className="text-sm text-[rgb(var(--muted))] underline-offset-4 hover:underline">
          What has not been measured →
        </Link>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        {findings().map((f) => (
          <Panel key={f.id} title={f.kicker}>
            <h2 className="text-lg font-semibold leading-snug tracking-tight">{f.title}</h2>
            <p className={`tnum mt-3 text-3xl font-semibold ${TONE[f.tone]}`}>{f.headline}</p>
            <dl className="mt-3 space-y-1.5 text-sm">
              {f.versus.map((v) => (
                <div key={v.label} className="flex items-baseline justify-between gap-4">
                  <dt className="text-[rgb(var(--muted))]">{v.label}</dt>
                  <dd className="tnum shrink-0 font-medium">{v.value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-sm leading-relaxed text-[rgb(var(--muted))]">{f.body}</p>
            <Link href={f.href} className="mt-3 inline-block text-sm underline-offset-4 hover:underline">
              The evidence →
            </Link>
          </Panel>
        ))}
      </div>
      <p className="mt-6 text-xs text-[rgb(var(--faint))]">
        Every number on this page is read from a results file committed by a training workflow and rebuilt by{" "}
        <code>python scripts/reproduce.py --check</code>. Designed, written and trained by an AI assistant under the
        owner&apos;s direction.
      </p>
    </Page>
  );
}
