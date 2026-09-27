"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, severityTone, Stat, statusTone } from "@/components/ui";
import { api, Incident } from "@/lib/api";
import { eventLabel, formatWhen, percent, STATUS_LABELS } from "@/lib/labels";

type Overview = {
  active_cameras: number;
  camera_count: number;
  incidents_today: number;
  critical_incidents: number;
  confirmed_incidents: number;
  false_positive_rate: number;
  trend: { hour: string; count: number }[];
  latest: Incident[];
};

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  function load() {
    api<Overview>("/api/system/overview").then(setData).catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
    const source = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/events/stream?access_token=${localStorage.getItem("token") || ""}`);
    source.onmessage = () => load();
    const timer = setInterval(load, 15000);
    return () => {
      source.close();
      clearInterval(timer);
    };
  }, []);

  const max = Math.max(1, ...(data?.trend.map((item) => item.count) || [1]));

  return (
    <Shell title="Overview">
      {error ? <p className="mb-4 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Active cameras" value={data ? `${data.active_cameras}/${data.camera_count}` : "—"} hint="Processing or online" />
        <Stat label="Incidents today" value={data?.incidents_today ?? "—"} />
        <Stat label="Critical today" value={data?.critical_incidents ?? "—"} />
        <Stat label="Confirmed today" value={data?.confirmed_incidents ?? "—"} />
        <Stat label="False positive rate" value={data ? percent(data.false_positive_rate) : "—"} hint="Among reviewed incidents" />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.1fr_1.4fr]">
        <section className="rounded-xl border border-line bg-white p-4">
          <h2 className="text-sm font-semibold">Incidents today</h2>
          <div className="mt-4 flex h-40 items-end gap-1">
            {(data?.trend || []).map((item) => (
              <div key={item.hour} className="flex flex-1 flex-col items-center justify-end">
                <div className="w-full rounded-sm bg-pine" style={{ height: `${(item.count / max) * 100}%`, minHeight: item.count ? 4 : 0 }} title={`${item.hour}: ${item.count}`} />
              </div>
            ))}
          </div>
          <div className="mt-2 flex justify-between text-[10px] text-slate-400">
            <span>00:00</span><span>12:00</span><span>23:00</span>
          </div>
        </section>
        <section className="overflow-auto rounded-xl border border-line bg-white">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="text-sm font-semibold">Latest incidents</h2>
            <Link href="/incidents" className="text-sm text-pine">View all</Link>
          </div>
          <table>
            <thead><tr><th>Time</th><th>Camera</th><th>Violation</th><th>Severity</th><th>Status</th></tr></thead>
            <tbody>
              {(data?.latest || []).map((item) => (
                <tr key={item.id}>
                  <td><Link className="text-pine" href={`/incidents/${item.id}`}>{formatWhen(item.started_at)}</Link></td>
                  <td>{item.camera_name}</td>
                  <td>{eventLabel(item.event_type)}</td>
                  <td><Badge value={item.severity} tone={severityTone(item.severity)} /></td>
                  <td><Badge value={STATUS_LABELS[item.status] || item.status} tone={statusTone(item.status)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </Shell>
  );
}
