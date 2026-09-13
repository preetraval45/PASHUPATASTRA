import { SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * The reading key, then a panel of rules per incident (R77).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={2} />
      <SkeletonPanel lines={4} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
