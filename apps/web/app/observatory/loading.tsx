import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * The feed panel with its source filter strip, then the status panel — the
 * shape of the observatory (R100).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <SkeletonBar key={i} className="h-7 w-24 rounded-full" />
        ))}
      </div>
      <SkeletonPanel lines={8} />
      <SkeletonPanel lines={3} />
    </div>
  );
}
