"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useApp } from "@/components/providers";
import Shell from "@/components/shell";
import { ErrorText, Kpi, SEVERITY, SeverityTag, Snapshot } from "@/components/ui";
import { api, Camera, Incident } from "@/lib/api";
import { useIncidentEvents } from "@/lib/live";
import { eventLabel, formatTime, percent, STATUS_LABELS } from "@/lib/labels";

type Overview = {
  active_cameras: number;
  camera_count: number;
  incidents_today: number;
  critical_incidents: number;
  confirmed_incidents: number;
  false_positive_rate: number;
  new_incidents: number;
  camera_incidents_today: Record<string, number>;
  trend: { hour: string; count: number; critical: number }[];
  peak: { hour: string; count: number; event_type: string; camera_name: string | null } | null;
};

const LIVE = new Set(["ONLINE", "AI_PROCESSING"]);

// A round axis top: 2, 4, … up to 10, then tens.
function axisMax(value: number) {
  if (value <= 10) return Math.max(2, Math.ceil(value / 2) * 2);
  return Math.ceil(value / 10) * 10;
}

export default function OverviewPage() {
  const { openIncident } = useApp();
  const [data, setData] = useState<Overview | null>(null);
  const [queue, setQueue] = useState<Incident[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [error, setError] = useState("");

  function load() {
    api<Overview>("/api/system/overview").then(setData).catch((err) => setError(err.message));
    api<{ items: Incident[] }>("/api/incidents?status=NEW&limit=6").then((page) => setQueue(page.items)).catch(() => undefined);
    api<Camera[]>("/api/cameras").then(setCameras).catch(() => undefined);
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);
  useIncidentEvents(load, 800);

  const trend = data?.trend || [];
  const top = axisMax(Math.max(0, ...trend.map((item) => item.count)));

  return (
    <Shell title="Overview">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-4">
        <Kpi dark label="Active cameras" value={data?.active_cameras ?? "—"} unit={data ? `/${data.camera_count}` : undefined} hint="Processing or online" />
        <Kpi label="Incidents today" value={data?.incidents_today ?? "—"} hint={data ? `${data.new_incidents} still waiting for a person` : undefined} />
        <Kpi label="Critical today" accent="crimson" value={data?.critical_incidents ?? "—"} hint="Act on these first" />
        <Kpi label="Confirmed today" value={data?.confirmed_incidents ?? "—"} hint="Marked real by an operator" />
        <Kpi label="False positive rate" value={data ? percent(data.false_positive_rate) : "—"} hint="Among reviewed incidents" />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="panel flex flex-col gap-[18px] px-6 py-[22px]">
          <div className="flex flex-wrap items-start gap-4">
            <div className="flex-1">
              <h2 className="text-base font-semibold">Incidents today</h2>
              <p className="text-[13px] text-bark-500">Per hour, factory time</p>
            </div>
            <div className="flex gap-3.5 text-xs text-bark-600">
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: SEVERITY.CRITICAL.bar }} />Critical</span>
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-gold-500" />High &amp; lower</span>
            </div>
          </div>
          <div className="flex items-stretch gap-2.5">
            <div className="-mt-1.5 flex h-60 w-5 flex-col justify-between text-right font-mono text-[10.5px] text-bark-300" aria-hidden="true">
              <span>{top}</span><span>{top / 2}</span><span>0</span>
            </div>
            <div
              role="group"
              aria-label="Incidents per hour today"
              className="relative flex h-60 flex-1 items-end gap-[2px] border-b border-t border-b-[#D9C7A6] border-t-line-soft"
            >
              <span className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-[#F1E9DC]" aria-hidden="true" />
              {trend.map((item, index) => {
                const other = item.count - item.critical;
                return (
                  <div
                    key={item.hour}
                    tabIndex={0}
                    aria-label={`${item.hour}: ${item.count} alerts, ${item.critical} critical`}
                    className="group relative flex h-full flex-1 flex-col items-center justify-end rounded-t outline-none hover:bg-gold-500/10 focus-visible:bg-gold-500/10"
                  >
                    {item.count ? <span className="mb-1 font-mono text-[10.5px] font-medium text-gold-800">{item.count}</span> : null}
                    {other ? <span className="w-[72%] max-w-[26px] rounded-t-[3px] bg-gold-bar motion-safe:transition-[height] motion-safe:duration-700" style={{ height: `${(other / top) * 100}%` }} /> : null}
                    {item.critical ? <span className={`w-[72%] max-w-[26px] motion-safe:transition-[height] motion-safe:duration-700 ${other ? "mt-[2px]" : "rounded-t-[3px]"}`} style={{ height: `${(item.critical / top) * 100}%`, background: SEVERITY.CRITICAL.bar }} /> : null}
                    <span className={`pointer-events-none absolute bottom-full z-10 mb-1.5 hidden whitespace-nowrap rounded bg-ink px-2 py-1 text-xs text-husk-100 shadow group-hover:block group-focus-visible:block ${index < 3 ? "left-0" : index > trend.length - 4 ? "right-0" : "left-1/2 -translate-x-1/2"}`}>
                      <span className="font-semibold text-white">{item.count}</span> at {item.hour}
                      {item.critical ? <span className="text-crimson-300"> · {item.critical} critical</span> : null}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="flex justify-between pl-[30px] font-mono text-[11px] text-bark-300" aria-hidden="true">
            <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
          </div>
          <p className="border-t border-dashed border-line pt-3.5 text-[13px] text-bark-600">
            {data?.peak ? (
              <>Peak at <strong className="text-bark-800">{data.peak.hour}</strong> — {data.peak.count} {data.peak.count === 1 ? "alert" : "alerts"}, mostly <strong className="text-bark-800">{eventLabel(data.peak.event_type)}</strong>{data.peak.camera_name ? <> on {data.peak.camera_name}</> : null}.</>
            ) : (
              "No alerts yet today."
            )}
          </p>
        </section>

        <section className="panel flex flex-col overflow-hidden">
          <div className="flex items-center gap-2.5 px-[22px] pb-3.5 pt-5">
            <h2 className="flex-1 text-base font-semibold">Awaiting review</h2>
            <span className="text-xs text-bark-500">{data?.new_incidents ?? 0} new</span>
            <Link href="/incidents?status=NEW" className="link text-[13px]">View all →</Link>
          </div>
          {queue.length === 0 ? <p className="border-t border-line-soft px-[22px] py-4 text-[13px] text-bark-500">Nothing waiting. Every alert has been reviewed.</p> : null}
          {queue.map((item) => (
            <button key={item.id} onClick={() => openIncident(item.id)} className="flex items-center gap-3.5 rounded-none border-t border-line-soft bg-transparent px-[22px] py-[11px] text-left text-bark-800 hover:bg-gold-50">
              <span className="relative h-[42px] w-16 shrink-0 overflow-hidden rounded-md">
                {item.snapshot_uri ? <Snapshot path={`/api/incidents/${item.id}/snapshot`} alt="" placeholder="" className="absolute inset-0 h-full w-full" /> : <span className="absolute inset-0 bg-stripes" />}
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-sm font-semibold">{eventLabel(item.event_type)}</span>
                <span className="truncate text-[12.5px] text-bark-500">{item.camera_name}{item.zone_name ? ` · ${item.zone_name}` : ""}</span>
              </span>
              <span className="flex flex-col items-end gap-[5px]">
                <SeverityTag severity={item.severity} />
                <span className="font-mono text-[11.5px] text-bark-400">{formatTime(item.started_at)}</span>
              </span>
            </button>
          ))}
        </section>
      </div>

      <section className="panel flex flex-col gap-3.5 px-[22px] py-5">
        <div className="flex items-center gap-2.5">
          <h2 className="flex-1 text-base font-semibold">Camera floor</h2>
          <Link href="/cameras" className="link text-[13px]">Manage →</Link>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
          {cameras.map((camera) => (
            <Link key={camera.id} href={`/cameras/${camera.id}`} className="flex items-center gap-3 rounded-[10px] border border-line-muted bg-cream p-3 text-bark-800 transition-colors hover:border-gold-500">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${LIVE.has(camera.status) ? "bg-leaf-600" : "bg-[#B7A893]"}`} aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13.5px] font-semibold">{camera.name}</span>
                <span className="block text-xs text-bark-500">{STATUS_LABELS[camera.status] || camera.status} · {data?.camera_incidents_today[camera.id] || 0} alerts</span>
              </span>
            </Link>
          ))}
        </div>
      </section>
    </Shell>
  );
}
