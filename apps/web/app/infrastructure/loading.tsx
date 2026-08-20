import { SkeletonBar, SkeletonHeader, SkeletonPanel } from "@/components/ui";

/**
 * The map is the slowest page to assemble — a topology snapshot, then a
 * layout computed over it. A tally strip, a map-sized block and the table
 * beneath it, so the page does not jump when the real one lands.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <SkeletonHeader />
      <div className="flex flex-wrap gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonBar key={i} className="h-4 w-24" />
        ))}
      </div>
      <SkeletonBar className="h-56 w-full rounded-lg" />
      <SkeletonPanel lines={4} />
    </div>
  );
}
