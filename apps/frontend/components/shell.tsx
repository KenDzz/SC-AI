"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearSession, getUser, User } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/cameras", label: "Cameras" },
  { href: "/rules", label: "Rules" },
  { href: "/incidents", label: "Incidents" },
  { href: "/evaluation", label: "Evaluation" },
];

export default function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState("DEMO");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const current = getUser();
    if (!current) {
      router.replace("/login");
      return;
    }
    setUser(current);
    api<{ ai_mode: string; worker_connected: boolean }>("/api/system/info")
      .then((info) => {
        setMode(info.ai_mode || "DEMO");
        setConnected(info.worker_connected);
      })
      .catch(() => undefined);
  }, [router, path]);

  if (!user) return <div className="p-8 text-sm text-slate-500">Loading…</div>;

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="flex flex-col bg-ink text-stone-100 md:min-h-screen">
        <div className="px-5 py-6">
          <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">Coffee factory</div>
          <div className="mt-1 text-lg font-semibold leading-tight">Safety Monitor</div>
        </div>
        <nav className="flex gap-1 overflow-auto px-3 md:block md:space-y-1">
          {LINKS.map((link) => {
            const active = link.href === "/" ? path === "/" : path.startsWith(link.href);
            return (
              <Link key={link.href} href={link.href} className={`block whitespace-nowrap rounded-md px-3 py-2 text-sm ${active ? "bg-white/10 text-white" : "text-stone-300 hover:bg-white/5"}`}>
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto px-5 py-5 text-sm">
          <div className="font-medium">{user.full_name}</div>
          <div className="text-xs text-stone-400">{user.role.replace("_", " ")}</div>
          <button
            className="mt-3 text-xs text-emerald-200"
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <div>
        <div className={`px-6 py-2 text-sm ${mode === "DEMO" ? "bg-amber-100 text-amber-950" : "bg-emerald-100 text-emerald-950"}`}>
          AI Mode: {mode}
          {mode === "DEMO" ? " — demonstration labels, not a trained factory model." : " — running the configured detector."}
          {connected ? "" : " Worker is still connecting."}
        </div>
        <header className="flex items-end justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-semibold text-ink">{title}</h1>
            <p className="text-sm text-slate-500">AI raises an alert. A person decides what it means.</p>
          </div>
        </header>
        <main className="px-6 pb-10">{children}</main>
      </div>
    </div>
  );
}
