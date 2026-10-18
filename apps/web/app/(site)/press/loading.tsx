import { SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * The paragraph, the figures, then the screenshots (R109).
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={5} />
      <SkeletonPanel lines={4} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
