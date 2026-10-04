/**
 * Finding indicators in rendered text (R78) — the page's half.
 *
 * The lookup happens in Python and the spans have to be known at render time
 * in TypeScript, so there are two implementations of one definition. What
 * stops them disagreeing is `packages/core/pashupatastra/indicators.json`:
 * every case in it runs against both, here in `indicators.test.ts` and there
 * in `testindicators.py`. A change to one that the other does not make fails
 * a suite rather than quietly marking up the wrong thing.
 *
 * The rule, and the reason for it: this runs over every identifier the console
 * renders, and the dangerous mistake is the permissive one. `j.rivera` is an
 * account in this estate, and a domain rule loose enough to match it would
 * make a public page an interface for asking which accounts exist. An
 * unrecognised suffix is **not** a domain rather than a guess.
 */

export type IndicatorKind = "ipv4" | "domain" | "md5" | "sha1" | "sha256" | "cve";

export interface Span {
  value: string;
  kind: IndicatorKind;
  start: number;
  end: number;
}

const HASH_KINDS: Record<number, IndicatorKind> = { 32: "md5", 40: "sha1", 64: "sha256" };

/** Kept identical to `SUFFIXES` in the Python module; the shared cases cover
 *  the entries that matter, and `thing.zzzzz` is the case that proves the list
 *  is consulted rather than the pattern trusted. */
const SUFFIXES = new Set(
  `com net org edu gov mil int info biz io ai co me tv cc ly sh dev app
   cloud online site xyz top club shop store live link click icu work
   uk us ca au de fr nl ru cn jp in br it es se no fi dk pl ch at be cz
   ie nz za kr mx ar cl pt gr hu ro bg hr rs ua tr il sa ae sg hk tw th
   vn id my ph pk bd lk np ir eg ng ke gh tz ug ma dz tn`.split(/\s+/),
);

const OCTET = "(?:25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)";
const IPV4 = `(?<![\\w.])(${OCTET}(?:\\.${OCTET}){3})(?![\\w.])`;
const HASH = "(?<![\\w])([a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})(?![\\w])";
const CVE = "(?<![\\w-])(CVE-\\d{4}-\\d{4,7})(?![\\w-])";
const DOMAIN =
  "(?<![\\w.@-])((?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\\.)+[a-zA-Z]{2,24})(?![\\w-])";

// Order matters, and matches the Python module's: a 32-character hex run is a
// hash and not four labels, and a CVE is claimed before anything else can take
// its digits.
const PATTERNS: { source: string; kind: IndicatorKind | null; flags: string }[] = [
  { source: CVE, kind: "cve", flags: "gi" },
  { source: HASH, kind: null, flags: "g" },
  { source: IPV4, kind: "ipv4", flags: "g" },
  { source: DOMAIN, kind: "domain", flags: "g" },
];

function hasKnownSuffix(domain: string): boolean {
  const suffix = domain.split(".").pop();
  return suffix !== undefined && SUFFIXES.has(suffix.toLowerCase());
}

/** What this string is, whole. `null` for anything not unambiguously one of
 *  the kinds — including every entity key this console uses. */
export function classify(value: string): IndicatorKind | null {
  const candidate = (value ?? "").trim();
  if (!candidate) return null;
  for (const { source, kind, flags } of PATTERNS) {
    const whole = new RegExp(`^(?:${source})$`, flags.replace("g", ""));
    if (!whole.test(candidate)) continue;
    if (kind === "cve") return kind;
    if (kind === null) return HASH_KINDS[candidate.length] ?? null;
    if (kind === "domain" && !hasKnownSuffix(candidate)) return null;
    return kind;
  }
  return null;
}

/** Every indicator inside a longer string, in the order they appear. */
export function scan(text: string): Span[] {
  const found: Span[] = [];
  const taken: [number, number][] = [];

  for (const { source, kind, flags } of PATTERNS) {
    const pattern = new RegExp(source, flags);
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text ?? "")) !== null) {
      const value = match[1];
      const start = match.index + match[0].indexOf(value);
      const end = start + value.length;
      if (taken.some(([otherStart, otherEnd]) => start < otherEnd && otherStart < end)) continue;
      const resolved = kind === null ? HASH_KINDS[value.length] : kind;
      if (!resolved) continue;
      if (resolved === "domain" && !hasKnownSuffix(value)) continue;
      taken.push([start, end]);
      found.push({ value, kind: resolved, start, end });
    }
  }

  return found.sort((a, b) => a.start - b.start);
}

/** The text split into the pieces an interface marks up: plain runs and
 *  indicators, in order, covering the whole string with nothing lost. */
export function split(text: string): ({ text: string } | Span)[] {
  const pieces: ({ text: string } | Span)[] = [];
  let cursor = 0;
  for (const span of scan(text)) {
    if (span.start > cursor) pieces.push({ text: text.slice(cursor, span.start) });
    pieces.push(span);
    cursor = span.end;
  }
  if (cursor < text.length) pieces.push({ text: text.slice(cursor) });
  return pieces;
}
