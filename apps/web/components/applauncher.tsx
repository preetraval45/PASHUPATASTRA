"use client";

import Link from "next/link";
import { useState } from "react";

import { useAccount } from "@/components/account";
import { Icon } from "@/components/sidebar";

/**
 * Every part of the product as an app, the way an ERP's home screen lays its
 * modules out: one tile each, grouped, searchable. A signed-in member's own
 * company apps come first; administrators also see Settings.
 */
type App = { href: string; title: string; blurb: string; icon: Parameters<typeof Icon>[0]["name"]; hue: string };

const GROUPS: { title: string; apps: App[] }[] = [
  {
    title: "Investigate",
    apps: [
      { href: "/ask", title: "Sati AI", blurb: "Ask about any attack or defence", icon: "chat", hue: "57 135 229" },
      { href: "/incidents", title: "Incidents", blurb: "Live attacks and investigations", icon: "alert", hue: "230 103 103" },
      { href: "/observatory", title: "Observatory", blurb: "Every public threat feed", icon: "radar", hue: "213 81 129" },
      { href: "/world", title: "World threats", blurb: "The global picture, daily", icon: "globe", hue: "25 158 112" },
    ],
  },
  {
    title: "Learn",
    apps: [
      { href: "/training", title: "Training", blurb: "Levels, games and labs", icon: "cap", hue: "144 133 233" },
      { href: "/models", title: "Sati models", blurb: "Nine models, measured", icon: "cube", hue: "201 133 0" },
      { href: "/findings", title: "Findings", blurb: "What the research showed", icon: "news", hue: "57 135 229" },
    ],
  },
  {
    title: "Operate",
    apps: [
      { href: "/overview", title: "Overview", blurb: "The console at a glance", icon: "grid", hue: "25 158 112" },
      { href: "/analytics", title: "Analytics", blurb: "Activity, risk and usage", icon: "chart", hue: "217 89 38" },
      { href: "/actions", title: "Actions", blurb: "What can run, under policy", icon: "bolt", hue: "201 133 0" },
      { href: "/detections", title: "Detections", blurb: "Rules drafted from incidents", icon: "shield", hue: "144 133 233" },
    ],
  },
];

export function AppLauncher() {
  const { me } = useAccount();
  const [find, setFind] = useState("");
  const company: App[] = (me?.orgs ?? []).flatMap((o) => [
    { href: `/company/${o.id}`, title: o.name, blurb: "Policies and required training", icon: "shield" as const, hue: "57 135 229" },
    ...(o.role !== "employee"
      ? [{ href: `/team/${o.id}`, title: "Team", blurb: `${o.name}'s people and progress`, icon: "users" as const, hue: "25 158 112" }]
      : []),
  ]);
  const groups = [
    ...(company.length ? [{ title: "Your company", apps: company }] : []),
    ...GROUPS,
    {
      title: "You",
      apps: [
        { href: me ? "/account" : "/login", title: me ? "Account" : "Sign in", blurb: me ? "Profile, security, companies" : "Save your progress", icon: "user" as const, hue: "126 136 149" },
        ...(me?.platform_admin
          ? [{ href: "/admin", title: "Settings", blurb: "Users & companies", icon: "gear" as const, hue: "126 136 149" }]
          : []),
      ],
    },
  ];
  const q = find.trim().toLowerCase();

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label text-[rgb(var(--astra))]">Apps</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            {me && me.user.provider !== "guest" ? `Welcome, ${me.user.name.split(" ")[0]}` : "Everything in Pashupatastra"}
          </h1>
        </div>
        <input
          value={find}
          onChange={(e) => setFind(e.target.value)}
          placeholder="Find an app"
          className="w-full max-w-xs rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-3.5 py-2 text-sm outline-none focus:border-[rgb(var(--astra))]/60"
        />
      </header>
      {groups.map((g) => {
        const apps = g.apps.filter((a) => !q || `${a.title} ${a.blurb}`.toLowerCase().includes(q));
        if (!apps.length) return null;
        return (
          <section key={g.title}>
            <h2 className="label mb-3">{g.title}</h2>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {apps.map((a) => (
                <li key={a.href}>
                  <Link
                    href={a.href}
                    className="focusable lift group flex h-full flex-col items-center rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-3 py-5 text-center transition hover:border-[rgb(var(--edge-strong))]"
                  >
                    <span
                      aria-hidden="true"
                      className="inline-flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-lg transition group-hover:scale-105"
                      style={{ background: `linear-gradient(135deg, rgb(${a.hue}), rgb(${a.hue} / 0.7))` }}
                    >
                      <Icon name={a.icon} className="h-7 w-7" />
                    </span>
                    <span className="mt-3 text-sm font-semibold">{a.title}</span>
                    <span className="mt-0.5 text-xs text-[rgb(var(--muted))]">{a.blurb}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
