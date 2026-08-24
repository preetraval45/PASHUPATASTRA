/**
 * Where a citation goes.
 *
 * Refs are not all one kind. `Evidence` used to send every one of them to
 * `/evidence/`, which is right only for event ids — a causal step, an entity
 * key or an incident id sent there renders "not found", and **a citation that
 * leads to a not-found is worse than one that is plainly unlinked**: it looks
 * checkable, so it gets taken on trust, and checking it fails.
 *
 * This lived in `chat.tsx` and was applied only there. `Evidence` kept the bug
 * its own docstring described, so `/evidence/INC-2026-0901` was reachable from
 * every hypothesis on the site. Shared now, so there is one answer to the
 * question rather than one per component.
 *
 * `incidentId` is optional because most callers render a citation without
 * knowing which incident it belongs to. Without it the in-page anchors cannot
 * be recognised, so those refs fall through to the entity or evidence route —
 * still a real page, rather than a fragment that scrolls nowhere.
 */
export function hrefFor(ref: string, incidentId?: string): string {
  if (ref.startsWith("audit:")) {
    // Anchored by timestamp. The audit list is newest-first and grows as
    // questions are asked, so a positional anchor points somewhere else by the
    // time the page renders.
    return `#${encodeURIComponent(ref)}`;
  }
  if (incidentId && ref.startsWith(`${incidentId}#chain-`)) {
    return `#chain-${ref.split("chain-")[1]}`;
  }
  if (incidentId && ref.startsWith(`${incidentId}#plan-`)) {
    return `#plan-${ref.split("plan-")[1]}`;
  }
  if (incidentId && ref.startsWith(`${incidentId}#hypothesis`)) {
    return "#diagnosis";
  }
  if (incidentId && ref === incidentId) return `/incidents/${encodeURIComponent(ref)}`;
  // An incident id, recognised by shape rather than by context. This is the
  // ref that was 404ing: a hypothesis cites the incident it belongs to, and no
  // caller of `Evidence` passes an incident id to compare against.
  if (/^INC-\d{4}-\d+$/.test(ref)) return `/incidents/${encodeURIComponent(ref)}`;
  // An entity key — `host:ws-0148`. Distinguished from an event id by the
  // colon, which event ids do not contain.
  if (ref.includes(":")) return `/entity/${encodeURIComponent(ref)}`;
  return `/evidence/${encodeURIComponent(ref)}`;
}

