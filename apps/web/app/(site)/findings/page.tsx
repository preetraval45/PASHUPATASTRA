import type { Metadata } from "next";
import Link from "next/link";

import { Filter, FilterRow } from "@/components/filter";
import { Page, Panel } from "@/components/ui";
import brahmacharini from "@/lib/models/brahmacharini.results.json";
import transformer from "@/lib/models/brahmacharini-transformer.results.json";
import chandraghanta from "@/lib/models/chandraghanta.results.json";
import katyayani from "@/lib/models/katyayani.results.json";
import live from "@/lib/models/katyayani-live.results.json";
import simtoreal from "@/lib/models/katyayani-simtoreal.results.json";
import kushmanda from "@/lib/models/kushmanda.results.json";
import kushmandaLarge from "@/lib/models/kushmanda-v3.results.json";
import mahagauri from "@/lib/models/mahagauri.results.json";
import diagnosis from "@/lib/models/rcaeval-diagnosis.results.json";
import siddhidatri from "@/lib/models/siddhidatri.results.json";
import skandamata from "@/lib/models/skandamata.results.json";
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
  // The variant the site presents as Mahagauri: the one within its safety budget.
  const mg = (mahagauri.pooled as Record<string, { premature_rate: number; confirmed_rate: number }>)[
    "mahagauri-v2 + 3σ agreement"
  ] ?? mahagauri.pooled["mahagauri-v0"];
  const alone = siddhidatri.mean_across_groups.shailaputri;

  const emb = brahmacharini.test as Record<string, { "recall@1": number }>;
  const mit = skandamata.test as Record<string, { "hit@1": number }>;
  const big = (transformer.test as Record<string, { "recall@1": number }>)["brahmacharini-v1 (transformer)"];
  const gl = (kushmandaLarge.sft?.grounded ?? {}) as Record<string, Record<string, Record<string, number>>>;

  const cicDetectors = cic.detectors as Record<string, { f1: number }>;
  const cicV2 = cicDetectors["chandraghanta-v2 (1% false-alarm budget)"];
  const cicV3 = cicDetectors["chandraghanta-v3 (fused, weight from held-out families)"];
  const fusion = (cic as { v3_fusion?: { weight: number } }).v3_fusion;

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
        {
          label: "a third system, on a live cluster · trained on real vs synthetic",
          value: `${f3(live.test["katyayani (trained on RCAEval, zero-shot)"]["rca@1"].value)} vs ${f3(live.test["katyayani-kaal-v0 (trained on Kaal, zero-shot)"]["rca@1"].value)}`,
        },
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
      title: "Safe, or useful — two models cannot yet be both",
      headline: pct(mg.premature_rate),
      versus: [
        { label: "Mahagauri — incidents declared over too early", value: pct(mg.premature_rate) },
        { label: "Mahagauri — recoveries it confirms", value: pct(mg.confirmed_rate) },
        { label: "Siddhidatri fusion F1 vs Shailaputri alone", value: `${f3(fused.f1)} vs ${f3(alone.f1)}` },
        { label: "fusion's false alarms vs Shailaputri alone", value: `${fused.false_alarms_per_1000.toFixed(1)} vs ${alone.false_alarms_per_1000.toFixed(1)}` },
      ],
      body:
        "Tuned honestly, Mahagauri now stays inside its 5% safety budget on servers it never saw: it rarely calls an incident over too early. But it confirms few recoveries, so most incidents still go back to a person — the model needs sharper signals, not a different threshold. Fusing three detectors bought recall with far more false alarms. Both are published, with what would fix them.",
      href: "/models#mahagauri-results",
      tone: "negative",
    },
    {
      id: "baseline",
      kicker: "Reported as found · ATT&CK, attackers never seen in training",
      title: "A plain TF-IDF classifier beat two of our models",
      headline: `${f3(emb["tf-idf logistic regression"]["recall@1"])} vs ${f3(emb["brahmacharini-v0"]["recall@1"])}`,
      versus: [
        { label: "behaviour → technique · TF-IDF + logistic regression", value: f3(emb["tf-idf logistic regression"]["recall@1"]) },
        { label: "behaviour → technique · Brahmacharini", value: f3(emb["brahmacharini-v0"]["recall@1"]) },
        { label: "the two fused, mix chosen on validation", value: f3(emb["brahmacharini-v0 + tf-idf (fused)"]?.["recall@1"] ?? 0) },
        { label: "behaviour → mitigation · TF-IDF vs Skandamata", value: `${f3(mit["tf-idf logistic regression"]["hit@1"])} vs ${f3(mit["skandamata-v0"]["hit@1"])}` },
      ],
      body:
        "The public Kaggle notebooks found it first, so the baseline was added to the training runs and the result reported. A model is only worth serving where it beats the strongest simple baseline. Brahmacharini still earns its place: it retrieves the passages behind every answer, which a classifier cannot, and fused with the classifier it beats both.",
      href: "/models#brahmacharini-results",
      tone: "negative",
    },
    {
      id: "bigger",
      kicker: "Reported as found · same data, same test",
      title: "Bigger models were not simply better",
      headline: `${f3(big["recall@1"])} vs ${f3(emb["brahmacharini-v0"]["recall@1"])}`,
      versus: [
        { label: "20M-parameter transformer encoder · Recall@1", value: f3(big["recall@1"]) },
        { label: "the served bag-of-words encoder · Recall@1", value: f3(emb["brahmacharini-v0"]["recall@1"]) },
        { label: "language model at 34M vs 17M · copies an ID right", value: `${f3(gl.kushmanda?.lookup?.exact_match ?? 0)} vs ${f3(g.kushmanda?.lookup?.exact_match ?? 0)}` },
        { label: "… and declines when it should", value: `${pct(gl.kushmanda?.unanswerable?.abstained ?? 0)} vs ${pct(g.kushmanda?.unanswerable?.abstained ?? 0)}` },
      ],
      body:
        "Both larger models were trained on Kaggle's GPUs with the epoch or step chosen on validation data. The larger encoder had too little data to learn from scratch. The larger language model copies identifiers better but declines less often when no passage holds the answer, and declining is what Sati depends on. The smaller models stay served.",
      href: "/models#kushmanda-results",
      tone: "negative",
    },
    {
      id: "novelty",
      kicker: "Reported as found · network intrusion, attack families never seen",
      title: "Rehearsing for new attacks with old ones did not prepare the model",
      headline: `${f3(cicV3?.f1 ?? 0)} vs ${f3(cicV2.f1)}`,
      versus: [
        { label: "the served detector, 1% false-alarm budget · F1", value: f3(cicV2.f1) },
        { label: "fused with a benign-only detector, tuned on held-out training families · F1", value: f3(cicV3?.f1 ?? 0) },
        { label: "weight it chose on the classifier", value: String(fusion?.weight ?? "—") },
      ],
      body:
        "To find a weight for new attacks without peeking at the test days, each attack family in the training days was hidden from the classifier in turn. Those families are mostly denial-of-service variants the classifier generalises across, so the rehearsal saw no need for the second detector. The real unseen attacks (botnets, infiltration, port scans, web attacks) needed it. The served model is unchanged.",
      href: "/models#chandraghanta-results",
      tone: "negative",
    },
    {
      id: "served",
      kicker: "Method · what the API actually runs",
      title: "We measured the model we serve, not only the one we trained",
      headline: `${f3(emb["served design (int8)"]?.["recall@1"] ?? 0)} → ${f3(emb["served design + pruned tf-idf (fused)"]?.["recall@1"] ?? 0)}`,
      versus: [
        { label: "the full model, as evaluated", value: f3(emb["brahmacharini-v0"]["recall@1"]) },
        { label: "the smaller int8 model the API can carry", value: f3(emb["served design (int8)"]?.["recall@1"] ?? 0) },
        { label: "the same, fused with a pruned TF-IDF classifier", value: f3(emb["served design + pruned tf-idf (fused)"]?.["recall@1"] ?? 0) },
      ],
      body:
        "A model squeezed to fit a lean serverless function is not the model in the paper, so its design was trained and tested on the same held-out attackers. It was weaker; fused with a small classifier it beat the full model. Then it was tried on real questions before shipping: it misread a defence question about ransomware on file shares, so that answer still comes from retrieval, and a test pins it.",
      href: "/models#brahmacharini-results",
      tone: "method",
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

const BAR: Record<Finding["tone"], string> = {
  positive: "bg-emerald-500/70",
  negative: "bg-amber-500/70",
  method: "bg-sky-500/70",
};

/** Said in words and a glyph, so the kind never rests on colour alone. */
const KIND: Record<Finding["tone"], { glyph: string; label: string; plural: string }> = {
  positive: { glyph: "▲", label: "Went for us", plural: "went for us" },
  negative: { glyph: "▼", label: "Went against us", plural: "went against us" },
  method: { glyph: "◆", label: "About method", plural: "are about method" },
};

/** A share between 0 and 1 gets a bar; anything else (a rate per 1000, "a vs b") is left as text. */
function share(value: string): number | null {
  const n = Number(value.replace("%", "")) / (value.endsWith("%") ? 100 : 1);
  return /^\d*\.?\d+%?$/.test(value) && n >= 0 && n <= 1 ? n : null;
}

export default async function FindingsPage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string | string[] }>;
}) {
  const all = findings();
  const raw = (await searchParams).kind;
  const kind = typeof raw === "string" && raw in KIND ? (raw as Finding["tone"]) : null;
  const shown = kind ? all.filter((f) => f.tone === kind) : all;
  const counts = (Object.keys(KIND) as Finding["tone"][]).map((t) => [t, all.filter((f) => f.tone === t).length] as const);
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
      <p className="mb-4 text-sm text-[rgb(var(--muted))]">
        {all.length} findings: {counts.map(([t, n], i) => (
          <span key={t}>
            {i > 0 && (i === counts.length - 1 ? " and " : ", ")}
            <span className={`font-medium ${TONE[t]}`}>{n}</span> {KIND[t].plural}
          </span>
        ))}
        .
      </p>
      <FilterRow label="Show">
        <Filter href="/findings" label="All" active={!kind} />
        {counts.map(([t, n]) => (
          <Filter key={t} href={`/findings?kind=${t}`} label={`${KIND[t].glyph} ${KIND[t].label} (${n})`} active={kind === t} />
        ))}
      </FilterRow>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        {shown.map((f) => (
          <Panel
            key={f.id}
            title={f.kicker}
            aside={
              <span className={`text-xs font-medium ${TONE[f.tone]}`}>
                <span aria-hidden="true">{KIND[f.tone].glyph}</span> {KIND[f.tone].label}
              </span>
            }
          >
            <h2 className="text-lg font-semibold leading-snug tracking-tight">{f.title}</h2>
            <p className={`tnum mt-3 text-3xl font-semibold ${TONE[f.tone]}`}>{f.headline}</p>
            <dl className="mt-4 space-y-2.5 text-sm">
              {f.versus.map((v) => {
                const bar = share(v.value);
                return (
                  <div key={v.label}>
                    <div className="flex items-baseline justify-between gap-4">
                      <dt className="text-[rgb(var(--muted))]">{v.label}</dt>
                      <dd className="tnum shrink-0 font-medium">{v.value}</dd>
                    </div>
                    {bar !== null && (
                      <div className="mt-1 h-1.5 rounded-full bg-[rgb(var(--raised))]" aria-hidden="true">
                        <div className={`h-1.5 rounded-full ${BAR[f.tone]}`} style={{ width: `${Math.max(2, bar * 100)}%` }} />
                      </div>
                    )}
                  </div>
                );
              })}
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
