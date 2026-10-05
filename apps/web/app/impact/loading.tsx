import { SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * Four stat tiles, then the provenance and the timeline (R107).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonPanel key={i} lines={1} />
        ))}
      </div>
      <SkeletonPanel lines={4} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
