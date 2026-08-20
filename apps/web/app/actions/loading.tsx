import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * A registry table, then the tier explanation beneath it.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={6} />
      <SkeletonPanel lines={3} />
    </div>
  );
}
