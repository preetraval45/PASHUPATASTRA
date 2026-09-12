/**
 * Fold runs of identical audit records into one row each (R98).
 *
 * One incident's trail carried `isolate_host: risk 67 → senior` 144 times —
 * every page view had written one, until R93 stopped it. The records are still
 * there, and the ledger is append-only, so the trail folds them on the way to
 * the screen instead: consecutive records with the same kind, summary and actor
 * become one row carrying `×N` and the span of time they cover, with every
 * individual record still reachable behind it. R56's shape, applied to the
 * audit trail.
 *
 * Consecutive only. Two identical lines separated by something else are two
 * events — an evaluation, an approval, another evaluation — and folding across
 * the approval would hide the order that makes the trail a trail.
 *
 * Pure over its input so `node --test` can hold it to the two properties that
 * matter: the group count for a known run, and that no record is lost between
 * input and output.
 */

export interface Foldable {
  kind: string;
  summary: string;
  actor: string;
  at: string;
}

export interface Fold<T extends Foldable> {
  /** The first record of the run — the one the row is drawn from. */
  record: T;
  /** Its position in the original list, which is what anchors are keyed by. */
  index: number;
  /** Every record in the run, including the first, in original order. */
  members: { record: T; index: number }[];
  /** How many records the row stands for. 1 means nothing was folded. */
  count: number;
  /** Earliest and latest `at` across the run — the list is newest-first, so
   *  the first member is the latest. */
  latest: string;
  earliest: string;
}

function sameLine(a: Foldable, b: Foldable): boolean {
  return a.kind === b.kind && a.summary === b.summary && a.actor === b.actor;
}

export function foldAudit<T extends Foldable>(records: T[]): Fold<T>[] {
  const folds: Fold<T>[] = [];
  records.forEach((record, index) => {
    const open = folds[folds.length - 1];
    if (open && sameLine(open.record, record)) {
      open.members.push({ record, index });
      open.count += 1;
      open.earliest = record.at < open.earliest ? record.at : open.earliest;
      open.latest = record.at > open.latest ? record.at : open.latest;
      return;
    }
    folds.push({
      record,
      index,
      members: [{ record, index }],
      count: 1,
      latest: record.at,
      earliest: record.at,
    });
  });
  return folds;
}
