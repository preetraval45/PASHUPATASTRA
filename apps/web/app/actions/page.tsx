import { getActions, riskBand } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ActionsPage() {
  const actions = await getActions();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Action registry</h1>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          The closed set of operations the system can perform. Anything not listed here cannot
          be executed — actions are registered, never generated.
        </p>
      </header>

      {!actions ? (
        <div className="panel p-6 text-sm text-[rgb(var(--muted))]">API unreachable.</div>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[rgb(var(--edge))] text-[rgb(var(--muted))]">
                <th className="p-3 font-medium">Action</th>
                <th className="p-3 font-medium">Base risk</th>
                <th className="p-3 font-medium">Rollback</th>
                <th className="p-3 font-medium">Expected post-state</th>
              </tr>
            </thead>
            <tbody>
              {actions.map((action) => {
                const band = riskBand(action.base_risk);
                return (
                  <tr key={action.id} className="border-b border-[rgb(var(--edge))] last:border-0">
                    <td className="p-3">
                      <div className="mono">{action.id}</div>
                      <div className="text-xs text-[rgb(var(--muted))]">{action.description}</div>
                    </td>
                    <td className="p-3">
                      <span className={`rounded border px-2 py-0.5 text-xs ${band.className}`}>
                        {action.base_risk}
                      </span>
                    </td>
                    <td className="mono p-3 text-xs">
                      {action.irreversible ? (
                        <span className="text-rose-400">irreversible</span>
                      ) : (
                        (action.rollback_action_id ?? "—")
                      )}
                    </td>
                    <td className="mono p-3 text-xs text-[rgb(var(--muted))]">
                      {Object.entries(action.expected_post_state)
                        .map(([k, v]) => `${k} ${v}`)
                        .join(", ") || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel p-5">
        <h2 className="label">Autonomy tiers</h2>
        <p className="mt-3 text-xs text-[rgb(var(--muted))]">
          Base risk is only the starting point. Effective risk rises with blast radius,
          production environment, low diagnostic confidence, and novelty — never falls.
        </p>
        <ul className="mono mt-3 space-y-1 text-xs">
          <li>
            <span className="text-emerald-400">0–30</span> autonomous
          </li>
          <li>
            <span className="text-amber-400">31–60</span> approval required
          </li>
          <li>
            <span className="text-orange-400">61–80</span> senior approval
          </li>
          <li>
            <span className="text-rose-400">81–100</span> never autonomous
          </li>
        </ul>
      </div>
    </div>
  );
}
