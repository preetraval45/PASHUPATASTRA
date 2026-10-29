/**
 * One accent per Sati model, as an "r g b" triplet for `rgb(var(--sp))`.
 *
 * Shared by Sati AI's specialists and the training levels, so a model keeps its
 * colour wherever it appears. The .sp-* classes in globals.css read it through
 * the --sp custom property; their text colour leans toward ink so amber and
 * lime stay readable on the light theme.
 */
export const HUES: Record<string, string> = {
  sati: "var(--astra)",
  brahmacharini: "99 102 241",
  skandamata: "16 185 129",
  katyayani: "245 158 11",
  kalaratri: "139 92 246",
  chandraghanta: "14 165 233",
  shailaputri: "236 72 153",
  siddhidatri: "6 182 212",
  mahagauri: "132 204 22",
  kushmanda: "148 163 184",
};

/** The style that sets a model's accent on an element. */
export function hue(name: string): Record<string, string> {
  return { "--sp": HUES[name.toLowerCase()] ?? HUES.sati };
}
