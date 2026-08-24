/**
 * What the thing is made of — on `/how-it-works`, and nowhere else.
 *
 * Names only. The version ranges and the list of manifest paths are gone: they
 * were the build describing its own working conditions, which is interesting to
 * the person who wrote it and to nobody else.
 *
 * Still **generated** from `package.json` and the three `pyproject.toml` files
 * by `scripts/buildinfo.py`, because R57's one real constraint survives the
 * redesign: a stack list claiming a dependency the repo does not have is the
 * same failure as an invented metric. Shorter is fine. Wrong is not.
 */

import info from "@/lib/buildinfo.generated.json";

export function BuiltWith() {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-x-8 gap-y-3">
        {info.groups.map((group) => (
          <div key={group.role} className="min-w-0">
            <p className="label mb-1.5">{group.role}</p>
            <p className="text-sm text-[rgb(var(--muted))]">
              {group.items.map((item) => item.name).join(" · ")}
            </p>
          </div>
        ))}
      </div>
      <p className="text-xs text-[rgb(var(--faint))]">
        Read from the repository&rsquo;s own manifests when the site is built,
        so this list cannot drift from what is actually installed.
      </p>
    </div>
  );
}
