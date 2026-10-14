"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/components/providers";
import { Emblem, LiveDot, Rule } from "@/components/ui";
import { API_URL, api, clearSession, getToken, getUser, Incident, User } from "@/lib/api";
import { emitIncident, useIncidentEvents } from "@/lib/live";
import { displayFont, eventLabel, formatDate, formatTime } from "@/lib/labels";

const LINKS = [
  { href: "/", label: "Overview", num: "I" },
  { href: "/cameras", label: "Cameras", num: "II" },
  { href: "/rules", label: "Rules", num: "III" },
  { href: "/incidents", label: "Incidents", num: "IV" },
  { href: "/evaluation", label: "Evaluation", num: "V" },
];

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

type ShellProps = {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  back?: { href: string; label: string };
};

export default function Shell({ title, children, actions, back }: ShellProps) {
  const router = useRouter();
  const path = usePathname();
  const { toast } = useApp();
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState("DEMO");
  const [connected, setConnected] = useState(true);
  const [newCount, setNewCount] = useState(0);
  const [now, setNow] = useState<Date | null>(null);
  const seen = useRef(new Set<string>());

  function loadNewCount() {
    api<{ total: number }>("/api/incidents?status=NEW&limit=1").then((page) => setNewCount(page.total)).catch(() => undefined);
  }

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
    loadNewCount();
  }, [router, path]);

  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // One stream per page view; every page listens through useIncidentEvents.
  useEffect(() => {
    if (!getToken()) return;
    const source = new EventSource(`${API_URL}/api/events/stream?access_token=${getToken()}`);
    source.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data) as { type?: string; incident?: Incident };
        const incident = data.incident || null;
        emitIncident(incident);
        // A fresh alert arrives NEW and still open; later updates of the same incident do not toast again.
        if (incident && incident.status === "NEW" && !incident.ended_at && !seen.current.has(incident.id)) {
          seen.current.add(incident.id);
          toast(`New alert · ${eventLabel(incident.event_type)}${incident.camera_name ? ` on ${incident.camera_name}` : ""}`, incident.id);
        }
      } catch {
        emitIncident(null);
      }
    };
    return () => source.close();
  }, [toast]);

  useIncidentEvents(loadNewCount, 800);

  if (!user) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="flex flex-col items-center gap-3 text-sm text-bark-500">
          <Emblem className="h-12 w-12 text-gold-500 motion-safe:animate-pulse" />
          Loading…
        </div>
      </div>
    );
  }

  const demo = mode === "DEMO";
  const signOut = () => {
    clearSession();
    router.replace("/login");
  };

  return (
    <div className="min-h-screen md:flex">
      <aside className="relative flex flex-col overflow-hidden bg-ink text-husk-100 md:sticky md:top-0 md:h-screen md:w-[264px] md:flex-none">
        <div className="flex items-center gap-3.5 px-[22px] pb-[22px] pt-[26px]">
          <Emblem className="h-[46px] w-[46px] shrink-0 text-gold-500" />
          <div className="flex min-w-0 flex-col gap-[3px]">
            <div className="whitespace-nowrap font-display text-[10.5px] tracking-[0.18em] text-gold-500">TRUNG NGUYÊN LEGEND</div>
            <div className="text-[17px] font-semibold tracking-[-0.01em] text-husk-50">Safety Monitor</div>
          </div>
        </div>
        <div className="mx-[22px] h-px bg-gradient-to-r from-gold-500/60 to-transparent" />
        <div className="hidden px-[22px] pb-2 pt-[22px] font-display text-[10px] tracking-[0.22em] text-husk-500 md:block">COFFEE FACTORY</div>
        <nav className="flex gap-0.5 overflow-auto px-3 py-3 md:flex-col md:py-0">
          {LINKS.map((link) => {
            const active = link.href === "/" ? path === "/" : path.startsWith(link.href);
            const badge = link.href === "/incidents" && newCount ? newCount : 0;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3.5 whitespace-nowrap rounded-lg px-3 py-[11px] transition-colors hover:bg-gold-500/10 hover:text-husk-50 ${active ? "bg-gold-500/15 text-gold-200" : "text-husk-300"}`}
              >
                <span className={`hidden w-6 font-display text-xs font-semibold md:inline ${active ? "text-gold-300" : "text-husk-700"}`}>{link.num}</span>
                <span className="flex-1 text-[14.5px] font-medium">{link.label}</span>
                {badge ? <span className="min-w-6 rounded-full bg-crimson-600 px-[7px] py-0.5 text-center text-[11px] font-bold text-[#FFF3EE]" aria-label={`${badge} new`}>{badge > 99 ? "99+" : badge}</span> : null}
              </Link>
            );
          })}
        </nav>
        <div className="relative hidden flex-1 md:block" aria-hidden="true">
          <Emblem className="pointer-events-none absolute -bottom-36 -left-28 h-[400px] w-[400px] text-gold-500/[0.16]" />
        </div>
        <div className="relative flex items-center gap-3 border-t border-gold-500/15 bg-ink px-[22px] py-4">
          <div className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-full border border-gold-500 text-xs font-semibold text-gold-300">{initials(user.full_name)}</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13.5px] font-semibold text-husk-50" title={user.full_name}>{user.full_name}</div>
            <div className="text-xs capitalize text-husk-500">{user.role.replace("_", " ").toLowerCase()}</div>
          </div>
          <button onClick={signOut} className="whitespace-nowrap rounded-md border border-gold-500/35 bg-transparent px-2.5 py-1.5 text-xs text-gold-400 hover:bg-gold-500/10">
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-[5] flex flex-wrap items-center gap-4 border-b border-line bg-[#FBF7F0]/90 px-4 py-3 backdrop-blur md:px-9">
          <div className={`flex items-center gap-2.5 rounded-full border py-1.5 pl-2.5 pr-3 ${demo ? "border-amber-200 bg-amber-50" : "border-leaf-200 bg-leaf-50"}`}>
            <LiveDot demo={demo} />
            <span className={`text-[13px] ${demo ? "text-amber-950" : "text-leaf-900"}`}>
              <strong className="font-bold">AI Mode: {mode}</strong>
              {demo ? " — demonstration labels, not a trained factory model" : " — running the configured detector"}
              {connected ? "" : " · worker still connecting"}
            </span>
          </div>
          <div className="flex-1" />
          {now ? (
            <div className="flex items-center gap-2 font-mono text-[12.5px] text-bark-500" aria-label="Factory time">
              <span>{formatDate(now)}</span>
              <span className="text-gold-500">◆</span>
              <span className="font-medium text-bark-800">{formatTime(now)}</span>
              <span>ICT</span>
            </div>
          ) : null}
        </header>

        <div className="flex w-full max-w-[1680px] flex-col gap-6 px-4 pb-12 pt-[30px] md:px-9">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex min-w-[260px] flex-1 flex-col gap-1.5">
              <div className="flex items-center gap-3">
                {back ? (
                  <>
                    <Link href={back.href} className="link text-[12.5px]">← {back.label}</Link>
                    <span className="text-[#D9C7A6]">/</span>
                  </>
                ) : null}
                <div className="font-display text-[11.5px] tracking-[0.24em] text-[#9A7333]">COFFEE FACTORY · SAFETY</div>
              </div>
              <h1 className={`m-0 text-[34px] font-semibold leading-tight tracking-[0.02em] text-bark-900 ${displayFont(title)}`}>{title}</h1>
              <p className="text-[14.5px] text-bark-500">AI raises an alert. A person decides what it means.</p>
            </div>
            {actions ? <div className="flex flex-wrap gap-2.5">{actions}</div> : null}
          </div>
          <Rule className="-mt-2" />
          {children}
        </div>
      </main>
    </div>
  );
}
