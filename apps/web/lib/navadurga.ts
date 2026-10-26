/**
 * The nine Sati models (adr/Navadurga). Names only — each is followed by its
 * job, and the job is what the page leads with.
 *
 * `results` is set only for a model that has been trained and evaluated; its
 * numbers come from the JSON the training workflow generated, never typed.
 */

import katyayani from "./models/katyayani.results.json";
import brahmacharini from "./models/brahmacharini.results.json";
import kalaratri from "./models/kalaratri.results.json";
import kalaratriBgl from "./models/kalaratri-bgl.results.json";
import chandraghanta from "./models/chandraghanta.results.json";
import shailaputri from "./models/shailaputri.results.json";

export type ModelStatus = "trained" | "training" | "planned";

export type Stage = "Observe" | "Remember" | "Understand" | "Explain" | "Act" | "Verify" | "Decide";

export interface SatiModel {
  n: number;
  id: string;
  name: string;
  nature: string;
  job: string;
  stage: Stage;
  data: string[];
  status: ModelStatus;
  task: string;
}

export const MODELS: SatiModel[] = [
  { n: 1, id: "sati-shailaputri", name: "Shailaputri", nature: "the steady foundation", job: "Metric anomaly detection — learns what normal looks like for every series", stage: "Observe", data: ["NAB", "SMD"], status: "training", task: "RP-60" },
  { n: 2, id: "sati-brahmacharini", name: "Brahmacharini", nature: "discipline and study", job: "Embeddings for memory — maps observed behaviour to the known technique it resembles", stage: "Remember", data: ["MITRE ATT&CK procedures"], status: "training", task: "RP-64" },
  { n: 3, id: "sati-chandraghanta", name: "Chandraghanta", nature: "the bell that warns", job: "Network intrusion alerting — flags attack traffic by family", stage: "Observe", data: ["UNSW-NB15", "CIC-IDS2017"], status: "planned", task: "RP-61" },
  { n: 4, id: "sati-kushmanda", name: "Kushmanda", nature: "the creator", job: "Writes the structured hypothesis and explanation — Sati's own language model", stage: "Explain", data: ["LogHub corpus", "incident text"], status: "planned", task: "RP-65" },
  { n: 5, id: "sati-skandamata", name: "Skandamata", nature: "the protecting mother", job: "Proposes the protective response — Dharma still authorises it", stage: "Act", data: ["MITRE ATT&CK mitigations"], status: "training", task: "RP-72" },
  { n: 6, id: "sati-katyayani", name: "Katyayani", nature: "the warrior who finds the adversary", job: "Root-cause ranking — names the service at fault and the fault type, citing the metric series", stage: "Understand", data: ["RCAEval"], status: "trained", task: "RP-58" },
  { n: 7, id: "sati-kalaratri", name: "Kalaratri", nature: "the night that dispels darkness", job: "Log anomaly detection — what hides in the noise", stage: "Observe", data: ["LogHub HDFS", "LogHub BGL"], status: "training", task: "RP-62" },
  { n: 8, id: "sati-mahagauri", name: "Mahagauri", nature: "calm restored", job: "Verification — confirms a system has truly returned to normal after an action", stage: "Verify", data: ["SMD incidents"], status: "training", task: "RP-71" },
  { n: 9, id: "sati-siddhidatri", name: "Siddhidatri", nature: "completion", job: "Fusion — combines the other eight into one calibrated verdict", stage: "Decide", data: ["outputs of 1–8"], status: "planned", task: "—" },
];

export const STAGES: Stage[] = ["Observe", "Remember", "Understand", "Explain", "Act", "Verify", "Decide"];

type Score = {
  n: number;
  "ac@1": number;
  "ac@1_ci": number[];
  "ac@3": number;
  "ac@3_ci": number[];
  "ac@5": number;
  "ac@5_ci": number[];
  "avg@5": number;
};

export interface RcaResults {
  dataset: { name: string; repo: string; revision: string; cases: number };
  splits: { scheme: string; fold: string; train_cases: number; sati: Score; baseline: Score; fault_accuracy?: number | null }[];
  pooled: Record<string, { sati: Score; baseline: Score }>;
  ablation_no_n_series?: { sati: Score };
  stress_re3?: { sati: Score; baseline: Score };
  example_explanation?: { case: string; service: string; reasons: { feature: string; contribution: number; value: number | null; series: string | null }[] };
  model_sha256: string;
}

export const KATYAYANI = katyayani as unknown as RcaResults;

type DetectMetrics = { f1: number; precision: number; recall: number; false_alarms_per_1000: number; mean_lead: number };

export interface DetectResults {
  pending?: string;
  dataset: { name: string; repo: string; revision: string; series: number; families: string[] };
  folds: { held_out: string; series: number; threshold: number; detectors: Record<string, DetectMetrics> }[];
  mean_across_families: Record<string, DetectMetrics>;
  model_sha256: string;
}

export const SHAILAPUTRI = shailaputri as unknown as DetectResults;

type BinaryMetrics = { precision: number; recall: number; f1: number; false_positive_rate: number };

export interface LogResults {
  pending?: string;
  dataset: { name: string; blocks: number; unit?: string; anomaly_share: number; split: { train: number; validation: number; test: number } };
  test: Record<string, BinaryMetrics>;
  weights_note: string;
}

export const KALARATRI = kalaratri as unknown as LogResults;
export const KALARATRI_BGL = kalaratriBgl as unknown as LogResults;

type FamilyRecall = { n: number; attack: boolean; seen_in_training: boolean } & Record<string, number | boolean>;

export interface NetResults {
  pending?: string;
  datasets: Record<"unsw" | "cic", {
    name: string;
    split: string;
    rows: { train: number; test: number };
    attack_share_test: number;
    detectors: Record<string, BinaryMetrics>;
    per_family: Record<string, FamilyRecall>;
    reference_random_split?: { rows_test: number; "chandraghanta-v0": BinaryMetrics };
  }>;
  weights_note: string;
}

export const CHANDRAGHANTA = chandraghanta as unknown as NetResults;

type Retrieval = { "recall@1": number; "recall@5": number; "recall@10": number; mrr: number; n: number };

export interface EmbedResults {
  pending?: string;
  dataset: { name: string; techniques: number; procedures: { train: number; validation: number; test: number }; test_sources_unseen: number };
  test: Record<string, Retrieval>;
}

export const BRAHMACHARINI = brahmacharini as unknown as EmbedResults;

/** A model counts as trained only when its results file says so. */
export function statusOf(model: SatiModel): ModelStatus {
  if (model.id === "sati-shailaputri") return SHAILAPUTRI.pending ? "training" : "trained";
  if (model.id === "sati-kalaratri") return KALARATRI.pending ? "training" : "trained";
  if (model.id === "sati-brahmacharini") return BRAHMACHARINI.pending ? "training" : "trained";
  if (model.id === "sati-chandraghanta") return CHANDRAGHANTA.pending ? "training" : "trained";
  return model.status;
}
