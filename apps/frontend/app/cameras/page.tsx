"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useApp } from "@/components/providers";
import Shell from "@/components/shell";
import { ErrorText, GhostButton, PrimaryButton, RecDot, Snapshot, StatusPill, Switch } from "@/components/ui";
import { api, Camera, getUser, Rule } from "@/lib/api";

const EMPTY = { code: "", name: "", area: "Packing Area", stream_type: "FILE", stream_url: "", ai_fps: 25, enabled: true, assigned_worker: "" };
const LIVE = new Set(["ONLINE", "AI_PROCESSING"]);

export default function CamerasPage() {
  const { toast } = useApp();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [alerts, setAlerts] = useState<Record<string, number>>({});
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [admin, setAdmin] = useState(false);
  useEffect(() => setAdmin(getUser()?.role === "ADMIN"), []);

  function load() {
    api<Camera[]>("/api/cameras").then(setCameras).catch((err) => setError(err.message));
    api<Rule[]>("/api/rules").then(setRules).catch(() => undefined);
    api<{ camera_incidents_today: Record<string, number> }>("/api/system/overview").then((data) => setAlerts(data.camera_incidents_today || {})).catch(() => undefined);
  }
  useEffect(load, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/cameras", { method: "POST", body: JSON.stringify({ ...form, assigned_worker: form.assigned_worker || null, ai_fps: Number(form.ai_fps) }) });
      setOpen(false);
      toast(`Camera added · ${form.name}`);
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the camera");
    }
  }

  async function setEnabled(camera: Camera, enabled: boolean) {
    setError("");
    try {
      const updated = await api<Camera>(`/api/cameras/${camera.id}`, { method: "PATCH", body: JSON.stringify({ enabled }) });
      setCameras((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the camera");
    }
  }

  const processing = cameras.filter((camera) => LIVE.has(camera.status)).length;

  return (
    <Shell title="Cameras" actions={admin ? <PrimaryButton onClick={() => setOpen(true)}>+ Add camera</PrimaryButton> : null}>
      <p className="text-sm text-bark-600">
        Each camera is an RTSP stream or an uploaded MP4 used like a camera. <strong className="text-bark-800">{processing}</strong> of {cameras.length} processing.
      </p>
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-[18px]">
        {cameras.map((camera) => {
          const live = LIVE.has(camera.status);
          const ruleCount = rules.filter((rule) => rule.camera_id === camera.id).length;
          return (
            <article key={camera.id} className="panel relative flex flex-col overflow-hidden transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_28px_rgba(42,30,21,.10)]">
              <div className="relative aspect-[2/1] overflow-hidden bg-stripes">
                <Snapshot
                  path={`/api/cameras/${camera.id}/snapshot?raw=true`}
                  alt=""
                  placeholder={`camera still · ${camera.area}`}
                  refreshMs={live ? 10000 : undefined}
                  className={`absolute inset-0 h-full w-full ${camera.enabled ? "" : "brightness-[.72] grayscale-[.6]"}`}
                />
                <span className={`absolute left-3 top-3 flex items-center gap-1.5 rounded bg-ink/80 px-2 py-1 font-mono text-[10.5px] tracking-[0.06em] ${live ? "text-[#F0B3A6]" : "text-husk-300"}`}>
                  {live ? <RecDot /> : null}
                  {live ? "LIVE" : "OFF"}
                </span>
                <span className="absolute right-3 top-3 rounded bg-ink/80 px-2 py-1 font-mono text-[10.5px] text-[#D9C7A6]">{camera.code}</span>
                <span className={`absolute inset-x-0 bottom-0 h-[3px] ${live ? "bg-leaf-600" : "bg-[#4A3A2C]"}`} />
              </div>
              <div className="flex items-center gap-3.5 px-[18px] pb-2.5 pt-4">
                <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  {/* The stretched link makes the whole card open the camera; the switch sits above it. */}
                  <Link href={`/cameras/${camera.id}`} className="truncate text-base font-semibold text-bark-800 after:absolute after:inset-0 hover:text-gold-700">{camera.name}</Link>
                  <span className="text-[13px] text-bark-500">{camera.area}</span>
                </div>
                <div className="relative z-[1]">
                  {admin ? <Switch checked={camera.enabled} onChange={(next) => setEnabled(camera, next)} label={camera.enabled ? `Disable ${camera.name}` : `Enable ${camera.name}`} /> : <StatusPill status={camera.status} />}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 px-[18px] pb-4">
                {[camera.stream_type, `${camera.ai_fps} FPS AI`, `${ruleCount} ${ruleCount === 1 ? "rule" : "rules"}`, `${alerts[camera.id] || 0} alerts today`].map((chip) => (
                  <span key={chip} className="rounded bg-paper px-2 py-[3px] font-mono text-[11px] text-bark-600">{chip}</span>
                ))}
              </div>
            </article>
          );
        })}
      </div>
      {open ? (
        <form onSubmit={create} className="fixed inset-0 z-20 grid place-items-center bg-ink/40 p-4">
          <div className="w-full max-w-lg rounded-xl border-t-2 border-gold-500 bg-surface p-6 shadow-xl">
            <h2 className="font-display text-lg font-semibold">Add camera</h2>
            <div className="mt-4 grid gap-3">
              <label className="text-sm font-medium">Code<input className="mt-1" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></label>
              <label className="text-sm font-medium">Name<input className="mt-1" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
              <label className="text-sm font-medium">Area<input className="mt-1" value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} required /></label>
              <label className="text-sm font-medium">Source
                <select className="mt-1" value={form.stream_type} onChange={(e) => setForm({ ...form, stream_type: e.target.value })}>
                  <option value="FILE">MP4 file</option>
                  <option value="RTSP">RTSP camera</option>
                </select>
              </label>
              <label className="text-sm font-medium">Stream URL<input className="mt-1 font-mono" value={form.stream_url} placeholder="rtsp://user:pass@camera/stream" onChange={(e) => setForm({ ...form, stream_url: e.target.value })} /></label>
              <label className="text-sm font-medium">AI FPS<input className="mt-1" type="number" min={1} max={30} value={form.ai_fps} onChange={(e) => setForm({ ...form, ai_fps: Number(e.target.value) })} /></label>
              <label className="text-sm font-medium">Assigned worker<input className="mt-1" value={form.assigned_worker} placeholder="Blank = any worker" onChange={(e) => setForm({ ...form, assigned_worker: e.target.value })} /></label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <GhostButton type="button" onClick={() => setOpen(false)}>Cancel</GhostButton>
              <PrimaryButton type="submit">Save</PrimaryButton>
            </div>
          </div>
        </form>
      ) : null}
    </Shell>
  );
}
