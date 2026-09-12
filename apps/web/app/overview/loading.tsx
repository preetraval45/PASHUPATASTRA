import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * Four stat tiles across the top, then the incident and activity panels — the
 * shape of the overview, so the eye does not have to re-find everything when
 * the numbers land (R13's rule, applied to the five routes that had no
 * loading state at all — R100).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonBar key={i} className="h-24 w-full rounded-lg" />
        ))}
      </div>
      <SkeletonPanel lines={5} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
