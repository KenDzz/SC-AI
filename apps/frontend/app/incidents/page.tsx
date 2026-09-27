"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, severityTone, statusTone } from "@/components/ui";
import { api, Camera, Incident, Zone } from "@/lib/api";
import { eventLabel, EVENT_LABELS, formatWhen, STATUS_LABELS } from "@/lib/labels";

export default function IncidentsPage() {
  const [items, setItems] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [filters, setFilters] = useState({ on_date: "", camera_id: "", zone_id: "", event_type: "", severity: "", status: "" });

  function load(next = filters) {
    const params = new URLSearchParams();
    Object.entries(next).forEach(([key, value]) => value && params.set(key, value));
    api<{ items: Incident[]; total: number }>(`/api/incidents?${params.toString()}`).then((page) => {
      setItems(page.items);
      setTotal(page.total);
    });
  }

  useEffect(() => {
    api<Camera[]>("/api/cameras").then(setCameras);
    api<Zone[]>("/api/zones").then(setZones);
    load();
  }, []);

  function update(key: string, value: string) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    load(next);
  }

  return (
    <Shell title="Incidents">
      <div className="mb-3 grid gap-2 md:grid-cols-6">
        <input type="date" value={filters.on_date} onChange={(e) => update("on_date", e.target.value)} />
        <select value={filters.camera_id} onChange={(e) => update("camera_id", e.target.value)}><option value="">All cameras</option>{cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select>
        <select value={filters.zone_id} onChange={(e) => update("zone_id", e.target.value)}><option value="">All zones</option>{zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}</select>
        <select value={filters.event_type} onChange={(e) => update("event_type", e.target.value)}><option value="">All violations</option>{Object.entries(EVENT_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <select value={filters.severity} onChange={(e) => update("severity", e.target.value)}><option value="">All severities</option>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((item) => <option key={item}>{item}</option>)}</select>
        <select value={filters.status} onChange={(e) => update("status", e.target.value)}><option value="">All statuses</option>{Object.entries(STATUS_LABELS).filter(([key]) => ["NEW", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"].includes(key)).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      </div>
      <p className="mb-2 text-xs text-slate-500">{total} incidents</p>
      <div className="overflow-auto rounded-xl border border-line bg-white">
        <table>
          <thead><tr><th>Time</th><th>Camera</th><th>Zone</th><th>Violation</th><th>Severity</th><th>AI confidence</th><th>Status</th><th>Evidence</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td><Link className="text-pine" href={`/incidents/${item.id}`}>{formatWhen(item.started_at)}</Link></td>
                <td>{item.camera_name}</td>
                <td>{item.zone_name || "—"}</td>
                <td>{eventLabel(item.event_type)}</td>
                <td><Badge value={item.severity} tone={severityTone(item.severity)} /></td>
                <td>{item.confidence === null ? "—" : `${Math.round(item.confidence * 100)}%`}</td>
                <td><Badge value={STATUS_LABELS[item.status] || item.status} tone={statusTone(item.status)} /></td>
                <td>{item.snapshot_uri ? "Snapshot" : "—"}{item.clip_uri ? " · Clip" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
