import { Badge, Ident, Offline, Page, Panel, statusForRisk } from "@/components/ui";
import { getActions } from "@/lib/api";

export const dynamic = "force-dynamic";

const TIERS = [
  { range: "0–30", label: "Autonomous", status: "ok", note: "an agent may act alone" },
  { range: "31–60", label: "Approval required", status: "warning", note: "an operator decides" },
  { range: "61–80", label: "Senior approval", status: "high", note: "a senior operator decides" },
  { range: "81–100", label: "Never autonomous", status: "critical", note: "no path to automatic execution" },
] as const;

export default async function ActionsPage() {
  const actions = await getActions();
  if (!actions) return <Offline />;

  return (
    <Page
      title="Action registry"
      description="The closed set of operations this system can perform. Anything not listed here cannot be executed — actions are registered, never generated."
    >
      <Panel title="Registered actions" aside={`${actions.length} actions`}>
        <div className="-mx-5 overflow-x-auto">
          <table className="stacked w-full min-w-[42rem] text-left text-sm">
            <caption className="sr-only">
              Registered actions with base risk, rollback, and expected post-state
            </caption>
            <thead>
              <tr className="border-b border-[rgb(var(--edge))] text-[rgb(var(--muted))]">
                <th scope="col" className="px-5 py-2 font-medium">Action</th>
                <th scope="col" className="px-5 py-2 font-medium">Base risk</th>
                <th scope="col" className="px-5 py-2 font-medium">Rollback</th>
                <th scope="col" className="px-5 py-2 font-medium">Expected post-state</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgb(var(--edge))]">
              {actions.map((action) => (
                <tr key={action.id}>
                  <td className="px-5 py-3 align-top">
                    <Ident>{action.id}</Ident>
                    <div className="mt-0.5 text-xs text-[rgb(var(--muted))]">
                      {action.description}
                    </div>
                  </td>
                  <td data-label="Base risk" className="px-5 py-3 align-top">
                    <Badge status={statusForRisk(action.base_risk)}>{action.base_risk}</Badge>
                  </td>
                  <td data-label="Rollback" className="px-5 py-3 align-top text-xs">
                    {action.irreversible ? (
                      <span className="text-[rgb(var(--crit))]">irreversible</span>
                    ) : (
                      <span className="mono">{action.rollback_action_id ?? "—"}</span>
                    )}
                  </td>
                  <td data-label="Post-state" className="mono px-5 py-3 align-top text-xs text-[rgb(var(--muted))]">
                    {Object.entries(action.expected_post_state)
                      .map(([k, v]) => `${k} ${v}`)
                      .join(", ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Autonomy tiers">
          <ul className="space-y-3">
            {TIERS.map((tier) => (
              <li key={tier.range} className="flex items-baseline gap-3 text-sm">
                <Badge status={tier.status}>{tier.range}</Badge>
                <span>{tier.label}</span>
                <span className="ml-auto text-xs text-[rgb(var(--faint))]">{tier.note}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="How effective risk is computed">
          <p className="text-sm text-[rgb(var(--muted))]">
            Base risk is only the starting point. It rises with blast radius, production
            environment, low diagnostic confidence, and novelty — and never falls. An action
            cannot argue its way into a lower tier.
          </p>
          <ul className="mt-4 space-y-1 text-xs text-[rgb(var(--muted))]">
            <li>Blast radius above threshold escalates a tier regardless of score.</li>
            <li>An action with no tested rollback cannot be autonomous.</li>
            <li>Irreversible actions are permanently outside autonomy.</li>
            <li>An agent may never exceed its own configured risk ceiling.</li>
          </ul>
        </Panel>
      </div>
    </Page>
  );
}
