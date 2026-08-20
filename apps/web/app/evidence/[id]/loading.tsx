import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * One observation and its provenance.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={2} />
      <SkeletonPanel lines={4} />
    </div>
  );
}
