import { SkeletonBar, SkeletonPanel } from "@/components/ui";

/** The rail, the conversation and the composer, in the shape they arrive in. */
export default function Loading() {
  return (
    <div className="flex min-h-0 flex-1" role="status" aria-label="Loading">
      <div className="hidden w-72 shrink-0 space-y-2 border-r border-[rgb(var(--edge))] p-3 lg:block">
        <SkeletonBar className="h-16 w-full rounded-lg" />
        <SkeletonBar className="h-16 w-full rounded-lg" />
        <SkeletonBar className="h-16 w-full rounded-lg" />
      </div>
      <div className="flex flex-1 flex-col">
        <div className="mx-auto w-full max-w-3xl flex-1 p-6">
          <SkeletonPanel lines={6} />
        </div>
        <div className="mx-auto w-full max-w-3xl p-4">
          <SkeletonBar className="h-14 w-full rounded-2xl" />
        </div>
      </div>
    </div>
  );
}
