import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * One entity: what it is, what it can reach, and what it has been saying.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={3} />
      <SkeletonPanel lines={2} />
      <SkeletonPanel lines={5} />
    </div>
  );
}
