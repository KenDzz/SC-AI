"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, ErrorText, GhostButton, PrimaryButton, statusTone } from "@/components/ui";
import { api, Camera, getUser } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/labels";

const EMPTY = { code: "", name: "", area: "Packing Area", stream_type: "FILE", stream_url: "", ai_fps: 25, enabled: true, assigned_worker: "" };

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [admin, setAdmin] = useState(false);
  useEffect(() => setAdmin(getUser()?.role === "ADMIN"), []);

  function load() {
    api<Camera[]>("/api/cameras").then(setCameras).catch((err) => setError(err.message));
  }
  useEffect(load, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/cameras", { method: "POST", body: JSON.stringify({ ...form, assigned_worker: form.assigned_worker || null, ai_fps: Number(form.ai_fps) }) });
      setOpen(false);
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the camera");
    }
  }

  return (
    <Shell title="Cameras">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-600">Each camera is an RTSP stream or an uploaded MP4 used like a camera.</p>
        {admin ? <PrimaryButton onClick={() => setOpen(true)}>Add camera</PrimaryButton> : null}
      </div>
      {error ? <div className="mb-3"><ErrorText>{error}</ErrorText></div> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {cameras.map((camera) => (
          <Link key={camera.id} href={`/cameras/${camera.id}`} className="rounded-xl border border-line bg-white p-4 hover:border-pine">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs text-slate-500">{camera.code}</div>
                <div className="text-lg font-semibold">{camera.name}</div>
                <div className="text-sm text-slate-600">{camera.area}</div>
              </div>
              <Badge value={STATUS_LABELS[camera.status] || camera.status} tone={statusTone(camera.status)} />
            </div>
            <div className="mt-3 flex gap-4 text-xs text-slate-500">
              <span>{camera.stream_type}</span>
              <span>{camera.ai_fps} FPS AI</span>
              <span>{camera.enabled ? "Enabled" : "Disabled"}</span>
            </div>
          </Link>
        ))}
      </div>
      {open ? (
        <form onSubmit={create} className="fixed inset-0 grid place-items-center bg-ink/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-5">
            <h2 className="text-lg font-semibold">Add camera</h2>
            <div className="mt-4 grid gap-3">
              <label className="text-sm">Code<input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></label>
              <label className="text-sm">Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
              <label className="text-sm">Area<input value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} required /></label>
              <label className="text-sm">Source
                <select value={form.stream_type} onChange={(e) => setForm({ ...form, stream_type: e.target.value })}>
                  <option value="FILE">MP4 file</option>
                  <option value="RTSP">RTSP camera</option>
                </select>
              </label>
              <label className="text-sm">Stream URL<input value={form.stream_url} placeholder="rtsp://user:pass@camera/stream" onChange={(e) => setForm({ ...form, stream_url: e.target.value })} /></label>
              <label className="text-sm">AI FPS<input type="number" min={1} max={30} value={form.ai_fps} onChange={(e) => setForm({ ...form, ai_fps: Number(e.target.value) })} /></label>
              <label className="text-sm">Assigned worker<input value={form.assigned_worker} placeholder="blank = any worker" onChange={(e) => setForm({ ...form, assigned_worker: e.target.value })} /></label>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <GhostButton type="button" onClick={() => setOpen(false)}>Cancel</GhostButton>
              <PrimaryButton type="submit">Save</PrimaryButton>
            </div>
          </div>
        </form>
      ) : null}
    </Shell>
  );
}
