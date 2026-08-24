import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel p-8">
      <h1 className="text-lg">Not found</h1>
      {/* The sections are not listed here any more. This copy named five of
          them and went stale the moment Ask, Observatory and Blue team were
          added — a not-found page confidently describing a console that no
          longer exists is worse than one that says less. The navigation above
          is already the list, and it cannot drift from itself. */}
      <p className="mt-2 text-sm text-[rgb(var(--muted))]">
        No such page. Everything the console holds is in the navigation above.
      </p>
      <Link
        href="/"
        className="focusable mt-4 inline-block rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
      >
        {/* The label followed the route. `/` was the Overview until R53 moved
            the console to `/overview`, and the button went on saying so — a
            small lie, on the page a reader lands on when something has already
            gone wrong. */}
        Back to the start
      </Link>
    </div>
  );
}
