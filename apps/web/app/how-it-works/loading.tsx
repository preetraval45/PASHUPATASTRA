import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * A run of prose panels — the seven stages, the tiers, the gates (R100).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={7} />
      <SkeletonPanel lines={4} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
