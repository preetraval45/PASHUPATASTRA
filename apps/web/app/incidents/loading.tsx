import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * The scenario cards, then the incidents themselves.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <div className="grid gap-3 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonBar key={i} className="h-32 w-full rounded-lg" />
        ))}
      </div>
      <SkeletonPanel lines={4} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
