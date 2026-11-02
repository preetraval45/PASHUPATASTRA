/**
 * What kind of real incident an id names, and the one line a list shows for it.
 *
 * The API builds live incidents from the feeds (`LIVE-…`) and past ones from the public record
 * (`PAST-…`), and the kind is the second part of the id. Read from the id rather than guessed
 * from the text, so the label cannot disagree with the rule that made the incident.
 */

export const KINDS = {
  KEV: { label: "Actively exploited", source: "CISA KEV" },
  NVD: { label: "Serious disclosure", source: "NIST NVD" },
  C2: { label: "Botnet infrastructure", source: "ThreatFox · Feodo Tracker" },
  RW: { label: "Ransomware campaign", source: "ransomware.live" },
  BREACH: { label: "Data breach", source: "Have I Been Pwned" },
  CAMPAIGN: { label: "Intrusion campaign", source: "MITRE ATT&CK" },
} as const;

export type Kind = keyof typeof KINDS;

const PATTERN = /^(LIVE|PAST)-(KEV|NVD|C2|RW|BREACH|CAMPAIGN)-/;

export function kindOf(id: string): Kind | null {
  const match = PATTERN.exec(id);
  return match ? (match[2] as Kind) : null;
}

/** True for incidents built from real records, live or past; false for a written scenario. */
export function isReal(id: string): boolean {
  return PATTERN.test(id);
}

export function isPast(id: string): boolean {
  return id.startsWith("PAST-");
}

/** The claim's first sentence, cut at a word if it is long. */
export function headline(statement: string, max = 170): string {
  const first = statement.split(/(?<=[.!?])\s/)[0] ?? statement;
  if (first.length <= max) return first;
  const cut = first.slice(0, max);
  return `${cut.slice(0, cut.lastIndexOf(" ") > 0 ? cut.lastIndexOf(" ") : max)}…`;
}

export function parseKind(value: string | string[] | undefined): Kind | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.toUpperCase() in KINDS ? (one.toUpperCase() as Kind) : null;
}
