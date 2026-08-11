import { Skeleton } from "@/components/ui";

/**
 * Shown while a server component fetches. A blank screen during an incident is
 * indistinguishable from a broken one, so the shape of the page arrives first
 * and the numbers follow.
 */
export default function Loading() {
  return (
    <div className="space-y-8" role="status" aria-label="Loading">
      <div className="h-8 w-48 rounded bg-[rgb(var(--panel))]" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]"
          />
        ))}
      </div>
      <Skeleton rows={3} />
    </div>
  );
}
