"use client";

import { useEffect, useRef, useState } from "react";
import { useApp } from "@/components/providers";
import Shell from "@/components/shell";
import { ErrorText, GhostButton, Segmented, SeverityTag, StatusPill } from "@/components/ui";
import { api, Camera, Incident, Zone } from "@/lib/api";
import { useIncidentEvents } from "@/lib/live";
import { eventLabel, EVENT_LABELS, formatDay, formatTime } from "@/lib/labels";

type Filters = { on_date: string; camera_id: string; zone_id: string; event_type: string; severity: string; status: string };

const EMPTY: Filters = { on_date: "", camera_id: "", zone_id: "", event_type: "", severity: "", status: "" };
const PAGE = 100;

const SEVERITY_TABS = [
  { value: "", label: "All" },
  { value: "CRITICAL", label: "Critical" },
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
];

const STATUS_TABS = [
  { value: "", label: "All" },
  { value: "NEW", label: "New" },
  { value: "CONFIRMED", label: "Confirmed" },
  { value: "FALSE_POSITIVE", label: "False positive" },
  { value: "RESOLVED", label: "Resolved" },
];

function confidenceColor(value: number) {
  if (value >= 0.8) return "bg-leaf-600";
  if (value >= 0.6) return "bg-gold-500";
  return "bg-[#B5564A]";
}

export default function IncidentsPage() {
  const { openIncident } = useApp();
  const [items, setItems] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [error, setError] = useState("");
  const shown = useRef(PAGE);

  function load(next = filters, limit = shown.current) {
    const params = new URLSearchParams();
    Object.entries(next).forEach(([key, value]) => value && params.set(key, value));
    params.set("limit", String(Math.min(200, limit)));
    api<{ items: Incident[]; total: number }>(`/api/incidents?${params.toString()}`)
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    api<Camera[]>("/api/cameras").then(setCameras).catch(() => undefined);
    api<Zone[]>("/api/zones").then(setZones).catch(() => undefined);
    // Links such as "View all →" open this page pre-filtered.
    const query = new URLSearchParams(window.location.search);
    const initial = { ...EMPTY };
    (Object.keys(EMPTY) as (keyof Filters)[]).forEach((key) => {
      initial[key] = query.get(key) || "";
    });
    setFilters(initial);
    load(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useIncidentEvents(() => load(), 800);

  function update(key: keyof Filters, value: string) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    shown.current = PAGE;
    load(next, PAGE);
  }

  return (
    <Shell title="Incidents">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Severity" options={SEVERITY_TABS} value={filters.severity} onChange={(value) => update("severity", value)} />
        <Segmented label="Status" options={STATUS_TABS} value={filters.status} onChange={(value) => update("status", value)} />
        <div className="flex-1" />
        <span className="text-[13px] text-bark-500"><strong className="text-bark-800">{total}</strong> incidents</span>
      </div>
      <div className="-mt-2 flex flex-wrap gap-2.5">
        <select aria-label="Camera" className="w-auto py-2 text-[13px]" value={filters.camera_id} onChange={(e) => update("camera_id", e.target.value)}>
          <option value="">All cameras</option>
          {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
        </select>
        <select aria-label="Zone" className="w-auto py-2 text-[13px]" value={filters.zone_id} onChange={(e) => update("zone_id", e.target.value)}>
          <option value="">All zones</option>
          {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
        </select>
        <select aria-label="Violation" className="w-auto py-2 text-[13px]" value={filters.event_type} onChange={(e) => update("event_type", e.target.value)}>
          <option value="">All violations</option>
          {Object.entries(EVENT_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
        <input aria-label="Date" type="date" className="w-auto py-2 text-[13px]" value={filters.on_date} onChange={(e) => update("on_date", e.target.value)} />
      </div>
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="panel overflow-auto">
        <table className="min-w-[1000px]">
          <thead>
            <tr><th>Time</th><th>Camera</th><th>Zone</th><th>Violation</th><th>Severity</th><th>AI confidence</th><th>Status</th><th aria-label="Open" /></tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={8} className="py-7 text-sm text-bark-500">No incidents match these filters.</td></tr>
            ) : null}
            {items.map((item) => (
              <tr key={item.id} onClick={() => openIncident(item.id)} className={`cursor-pointer ${item.status === "NEW" && item.severity === "CRITICAL" ? "bg-crimson-50" : ""}`}>
                <td>
                  <button className="flex flex-col items-start rounded-none bg-transparent p-0 text-left" onClick={(e) => { e.stopPropagation(); openIncident(item.id); }}>
                    <span className="font-mono text-[12.5px] text-gold-700">{formatTime(item.started_at)}</span>
                    <span className="text-[11px] font-normal text-bark-300">{formatDay(item.started_at)}</span>
                  </button>
                </td>
                <td className="text-[13.5px]">{item.camera_name}</td>
                <td className="text-[13.5px] text-bark-600">{item.zone_name || "—"}</td>
                <td className="text-[13.5px] font-medium">{eventLabel(item.event_type)}</td>
                <td><SeverityTag severity={item.severity} /></td>
                <td>
                  {item.confidence === null ? (
                    <span className="text-bark-400">—</span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <span className="h-[5px] w-24 overflow-hidden rounded-[3px] bg-line-muted">
                        <span className={`block h-full ${confidenceColor(item.confidence)}`} style={{ width: `${Math.round(item.confidence * 100)}%` }} />
                      </span>
                      <span className="w-[34px] font-mono text-xs">{Math.round(item.confidence * 100)}%</span>
                    </span>
                  )}
                </td>
                <td><StatusPill status={item.status} /></td>
                <td className="text-base text-gold-600" aria-hidden="true">›</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length < total ? (
        <div className="flex items-center justify-center gap-3 text-[13px] text-bark-500">
          Showing {items.length} of {total}
          {shown.current < 200 ? (
            <GhostButton onClick={() => { shown.current = 200; load(filters, 200); }}>Show more</GhostButton>
          ) : (
            <span>· narrow the filters to see older incidents</span>
          )}
        </div>
      ) : null}
    </Shell>
  );
}
