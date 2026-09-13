import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * A row of tactic columns, then the explanation beneath (R75).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonBar key={i} className="h-40 w-40 shrink-0 rounded-lg" />
        ))}
      </div>
      <SkeletonPanel lines={3} />
    </div>
  );
}
