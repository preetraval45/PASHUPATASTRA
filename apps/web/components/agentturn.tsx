/**
 * The provenance of one thing the agent said.
 *
 * An audit line reading "answered · gpt-oss-20b · 6062 tokens" records *that*
 * it answered. R22 asks for *why it said that*, and the difference is what is
 * underneath: the question, the reply, the prompt in force, and every lookup it
 * made on the way. Without that the trail proves a turn happened, which nobody
 * was in doubt about.
 *
 * Collapsed, because most of the time the summary is enough and an audit page
 * where every row is a paragraph is a page nobody reads to the bottom of.
 */

import type { AuditRecord } from "@/lib/api";
import { Ident } from "@/components/ui";

type TraceEntry = {
  hop: number;
  kind: string;
  name?: string;
  detail?: Record<string, unknown>;
  usage?: { input_tokens?: number; output_tokens?: number };
};

/** How each step is described in the trace, in words rather than field names. */
const STEP: Record<string, string> = {
  tool_call: "looked up",
  tool_result: "got back",
  refusal: "refused a tool it was not given",
  answer: "answered",
  format: "re-asked for the structured form",
  budget_exhausted: "ran out of budget",
};

/**
 * A citation, shortened for reading.
 *
 * An audit ref is an ISO timestamp, and four of them in a row is a wall of
 * `2026-08-21T13:28:14.796479+00:00` that hides the refs a reader can actually
 * act on. The incident prefix goes too: it is the same on every ref in a turn
 * about one incident, so it carries no information and costs a line of width.
 */
function short(ref: string): string {
  if (ref.startsWith("audit:")) return `audit ${ref.slice(6, 16)} ${ref.slice(17, 25)}`;
  const hash = ref.indexOf("#");
  return hash === -1 ? ref : ref.slice(hash + 1);
}

export function AgentTurn({ record }: { record: AuditRecord }) {
  const detail = record.detail as {
    asked?: string;
    answer?: string;
    model?: string;
    provider?: string;
    prompt_version?: string;
    prompt_digest?: string;
    evidence_refs?: string[];
    dropped_refs?: string[];
    proposed_action_id?: string | null;
    cached?: boolean;
    grounded?: boolean;
    trace?: TraceEntry[];
  };

  if (!detail?.asked) return null;
  const trace = detail.trace ?? [];

  return (
    <details className="mt-1 w-full">
      <summary className="focusable inline-block cursor-pointer rounded text-xs text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]">
        why it said that
      </summary>

      <div className="mt-2 space-y-3 border-l border-[rgb(var(--edge))] pl-3 text-xs">
        <div>
          <p className="text-[rgb(var(--faint))]">asked</p>
          {/* Typed by a visitor. React escapes it, and the API caps its length
              and strips control characters before it is ever stored — this is a
              permanent public record accepting text from anyone. */}
          <p className="break-words text-[rgb(var(--ink))]">{detail.asked}</p>
        </div>

        {detail.answer && (
          <div>
            <p className="text-[rgb(var(--faint))]">answered</p>
            <p className="whitespace-pre-wrap break-words">{detail.answer}</p>
          </div>
        )}

        {trace.length > 0 && (
          <div>
            <p className="text-[rgb(var(--faint))]">what it did</p>
            <ol className="mt-1 space-y-0.5">
              {trace.map((step, index) => (
                <li key={index} className="flex flex-wrap gap-x-2">
                  <span className="mono text-[rgb(var(--faint))]">
                    {step.hop}.{index}
                  </span>
                  <span>{STEP[step.kind] ?? step.kind}</span>
                  {step.name && <Ident>{step.name}</Ident>}
                  {step.detail?.entity_key ? (
                    <span className="mono text-[rgb(var(--faint))]">
                      {String(step.detail.entity_key)}
                    </span>
                  ) : null}
                  {step.usage?.output_tokens ? (
                    <span className="text-[rgb(var(--faint))]">
                      {(step.usage.input_tokens ?? 0) + step.usage.output_tokens} tokens
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        )}

        {(detail.evidence_refs?.length || detail.dropped_refs?.length) && (
          <div>
            <p className="text-[rgb(var(--faint))]">cited</p>
            <p className="mono break-words">
              {detail.evidence_refs?.map(short).join(", ") || "nothing"}
            </p>
            {detail.dropped_refs?.length ? (
              <p className="mono break-words text-[rgb(var(--warn))]">
                dropped as unresolvable: {detail.dropped_refs.join(", ")}
              </p>
            ) : null}
          </div>
        )}

        {detail.proposed_action_id && (
          <div>
            <p className="text-[rgb(var(--faint))]">proposed</p>
            <p>
              <Ident>{detail.proposed_action_id}</Ident> — queued for a human,
              nothing executed
            </p>
          </div>
        )}

        {/* The prompt is half of why any answer came out the way it did, so the
            version is recorded with every turn. The digest goes with it because
            the version is written by hand, and is therefore wrong exactly when
            someone edited the prompt and forgot to bump it. */}
        <p className="text-[rgb(var(--faint))]">
          <span className="mono">{detail.model}</span>
          {detail.provider && ` via ${detail.provider}`}
          {detail.prompt_version && ` · prompt v${detail.prompt_version}`}
          {detail.prompt_digest && (
            <span className="mono"> ({detail.prompt_digest})</span>
          )}
          {detail.cached && " · served from cache"}
        </p>
      </div>
    </details>
  );
}
