import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * The scoring explanation, then one card per scenario (R100).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={3} />
      <div className="grid gap-3 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonBar key={i} className="h-36 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}
