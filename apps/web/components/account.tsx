"use client";

import Link from "next/link";
import { useEffect, useSyncExternalStore } from "react";

import { load, snapshot, subscribe } from "@/lib/account";

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
export function AccountButton() {
  const { me, ready } = useAccount();
  if (!ready) return <span aria-hidden="true" className="h-8 w-8 rounded-full bg-[rgb(var(--raised))]" />;
  if (!me) {
    return (
      <Link
        href="/signin"
        className="focusable inline-flex h-8 items-center rounded-full bg-[rgb(var(--astra))] px-3.5 text-xs font-semibold text-white transition hover:brightness-110"
      >
        Sign in
      </Link>
    );
  }
  return (
    <Link
      href="/account"
      title={me.user.name}
      aria-label={`Your account, ${me.user.name}`}
      className="focusable inline-flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,rgb(var(--astra)),rgb(var(--astra)/0.55))] text-xs font-bold text-white ring-2 ring-[rgb(var(--astra))]/20"
    >
      {initials(me.user.name)}
    </Link>
  );
}
