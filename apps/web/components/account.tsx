"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { load, signOut, snapshot, subscribe } from "@/lib/account";

const SERVER = { token: null, me: null, ready: false };

/** The signed-in account, read anywhere. Starts loading the kept session on first use. */
export function useAccount() {
  const state = useSyncExternalStore(subscribe, snapshot, () => SERVER);
  useEffect(() => {
    load();
  }, []);
  return state;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("") || "?";
}

/** The header's account button: "Sign in", or the account's initials linking to /account. */
const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password", "/signin"];

export function AccountButton() {
  const { me, ready } = useAccount();
  const pathname = usePathname();
  // On the sign-in pages themselves the form is the call to action; a second "Sign in" is noise.
  if (!me && AUTH_PAGES.includes(pathname)) return null;
  if (!ready) return <span aria-hidden="true" className="h-8 w-8 rounded-full bg-[rgb(var(--raised))]" />;
  if (!me) {
    return (
      <Link
        href="/login"
        className="focusable inline-flex h-8 items-center rounded-full bg-[rgb(var(--astra))] px-3.5 text-xs font-semibold text-white transition hover:brightness-110"
      >
        Sign in
      </Link>
    );
  }
  return <AccountMenu />;
}

/** The signed-in menu: the account, its companies' dashboards, training, and signing out. */
function AccountMenu() {
  const { me } = useAccount();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  if (!me) return null;
  const item = "focusable flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-[rgb(var(--raised))]";
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu, ${me.user.name}`}
        className="focusable inline-flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,rgb(var(--astra)),rgb(var(--astra)/0.55))] text-xs font-bold text-white ring-2 ring-[rgb(var(--astra))]/20"
      >
        {initials(me.user.name)}
      </button>
      {open && (
        <div role="menu" className="rise absolute right-0 top-10 z-50 w-64 rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-1.5 shadow-2xl">
          <div className="border-b border-[rgb(var(--edge))] px-3 pb-2.5 pt-2">
            <p className="truncate text-sm font-semibold">{me.user.name}</p>
            <p className="truncate text-xs text-[rgb(var(--muted))]">{me.user.email ?? "Guest session"}</p>
          </div>
          <div className="py-1">
            <Link href="/account" role="menuitem" onClick={() => setOpen(false)} className={item}>Account settings</Link>
            {me.orgs
              .filter((o) => o.role !== "employee")
              .map((o) => (
                <Link key={o.id} href={`/team/${o.id}`} role="menuitem" onClick={() => setOpen(false)} className={item}>
                  <span className="min-w-0 truncate">Team · {o.name}</span>
                </Link>
              ))}
            <Link href="/training" role="menuitem" onClick={() => setOpen(false)} className={item}>My training</Link>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              signOut();
              router.push("/login");
            }}
            className={`${item} w-full border-t border-[rgb(var(--edge))] text-[rgb(var(--crit))]`}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
