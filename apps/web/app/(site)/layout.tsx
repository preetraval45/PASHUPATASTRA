import { ModeIndicator } from "@/components/chrome";
import { ConsoleFrame } from "@/components/sidebar";
import { getHealth } from "@/lib/api";

/**
 * The public pages, in the same frame as the console.
 *
 * They had their own website header until the owner's review: the site and the
 * console read as two products, and "Open the console" felt like leaving one
 * for the other. Now Home, How it works and Evaluation sit in the same rail as
 * Incidents and Sati AI, so the whole thing is one app a visitor can wander.
 * Kept as a separate route group only so these pages can diverge again.
 */
export default async function SiteLayout({ children }: { children: React.ReactNode }) {
  const health = await getHealth();
  return (
    <ConsoleFrame status={<ModeIndicator health={health} />}>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>
      </div>
    </ConsoleFrame>
  );
}
