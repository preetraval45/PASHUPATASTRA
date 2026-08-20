import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * A list of records, newest first.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={6} />
    </div>
  );
}
