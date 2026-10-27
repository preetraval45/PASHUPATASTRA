import Link from "next/link";

/**
 * One option in a link-driven filter row. A link rather than a button: the
 * filtered view is a URL, so it can be shared and works with scripts off.
 * `aria-current` carries the selection, so it is announced, not only tinted.
 */
export function Filter({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`focusable rounded-full border px-3 py-1.5 text-xs transition ${
        active
          ? "border-[rgb(var(--edge-strong))] bg-[rgb(var(--raised))] text-[rgb(var(--ink))]"
          : "border-[rgb(var(--edge))] text-[rgb(var(--muted))] hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
      }`}
    >
      {label}
    </Link>
  );
}

/** A labelled row of filters, so a screen reader hears what the options choose. */
export function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      <span className="label mr-1">{label}</span>
      {children}
    </div>
  );
}
