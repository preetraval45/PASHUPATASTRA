import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * Shown while one incident is fetched — including when switching between
 * scenarios, which is the navigation this exists for. The shape matches the
 * incident page: summary, causal chain, diagnosis, plan, timeline. Switching
 * used to leave the previous incident on screen until the next one arrived,
 * which reads as a click that did nothing.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <SkeletonPanel lines={4} />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-6">
          <SkeletonPanel lines={5} />
          <SkeletonPanel lines={3} />
        </div>
        <div className="space-y-6">
          <SkeletonPanel lines={4} />
          <SkeletonPanel lines={2} />
        </div>
      </div>
    </div>
  );
}
