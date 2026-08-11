import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel p-8">
      <h1 className="text-lg">Not found</h1>
      <p className="mt-2 text-sm text-[rgb(var(--muted))]">
        No such page. The console has Overview, Incidents, Infrastructure, Actions, and Audit.
      </p>
      <Link
        href="/"
        className="focusable mt-4 inline-block rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
      >
        Back to overview
      </Link>
    </div>
  );
}
