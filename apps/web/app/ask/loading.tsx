import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * One tall console with an incident picker above it (R100).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonBar className="h-9 w-64 rounded" />
      <SkeletonPanel lines={9} />
    </div>
  );
}
