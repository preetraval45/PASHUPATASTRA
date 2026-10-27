/**
 * How a results file's row names appear on the website.
 *
 * The results files keep every variant a model went through ("mahagauri-v1 +
 * 3σ agreement"), because the research paper compares them. The website shows
 * each of the nine models once, by its form's name, as the variant currently
 * served or recommended. Superseded variants are hidden here; they stay in the
 * paper and the model cards (docs/research/models/cards). Baselines keep their
 * own names.
 *
 * One table, so a model never has two names on one page, and a version label
 * never reaches a visitor.
 */

/** Result key → the name shown. Keys absent here are baselines, shown as written. */
const SHOWN: Record<string, string> = {
  "shailaputri-v0": "Shailaputri",
  "shailaputri-v1 onset-weighted": "Shailaputri",
  "brahmacharini-v0": "Brahmacharini",
  "chandraghanta-v2 (1% false-alarm budget)": "Chandraghanta",
  "chandraghanta-v0": "Chandraghanta, best-F1 threshold",
  "chandraghanta-v0 without TTL": "Chandraghanta, best-F1 threshold, without TTL fields",
  "kalaratri-v0": "Kalaratri",
  "Kalaratri v0": "Kalaratri",
  "skandamata-v0": "Skandamata",
  "mahagauri-v2 + 3σ agreement": "Mahagauri",
  "siddhidatri-v0": "Siddhidatri",
  "katyayani-kaal-v0 (zero-shot)": "Katyayani, trained on synthetic incidents",
  "katyayani-kaal-v0 (trained on Kaal, zero-shot)": "Katyayani, trained on synthetic incidents",
  "katyayani (trained on RCAEval, zero-shot)": "Katyayani",
  sati: "Katyayani",
};

/** Superseded variants: in the paper, not on the site. */
const HIDDEN = new Set([
  "shailaputri-v1",
  "brahmacharini-v1 (transformer)",
  "chandraghanta-v1 (either)",
  "mahagauri-v0",
  "mahagauri-v1 (upper-bound threshold)",
  "mahagauri-v1 + 3σ agreement",
  "mahagauri-v2 (out-of-fold, hold chosen)",
  "siddhidatri-v1 (at Shailaputri's false-alarm budget)",
]);

export function shownName(key: string): string {
  return SHOWN[key] ?? key.replace(/[-\s]v\d+\b/gi, "");
}

export function isShown(key: string): boolean {
  return !HIDDEN.has(key);
}

/** Whether a row is one of the nine models (bolded) rather than a baseline. */
export function isOurs(key: string): boolean {
  return key in SHOWN;
}

/** `Object.entries` with superseded variants removed. */
export function shownEntries<T>(record: Record<string, T>): [string, T][] {
  return Object.entries(record).filter(([k]) => isShown(k));
}

const FORMS = [
  "shailaputri", "brahmacharini", "chandraghanta", "kushmanda", "skandamata",
  "katyayani", "kalaratri", "mahagauri", "siddhidatri",
];

/** A served model's id ("sati-skandamata-serve-v0") → the form's name ("Skandamata").
 *  Ids that are not one of the nine (an external baseline) are shown as they are. */
export function servedName(id: string | null | undefined): string {
  if (!id) return "";
  const form = FORMS.find((f) => id.toLowerCase().includes(f));
  return form ? form[0].toUpperCase() + form.slice(1) : id;
}
