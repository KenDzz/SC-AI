"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, ErrorText, GhostButton, PrimaryButton, statusTone } from "@/components/ui";
import { api, Camera, getUser, imageUrl } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/labels";

type Check = { text: string; state: "violation" | "ok" | "unknown" };

const CHECK_TONES: Record<Check["state"], string> = { violation: "red", ok: "green", unknown: "slate" };

type ZoneState = { id: string; name: string; state: string; shift_pct: number };

const ZONE_STATES: Record<string, { label: (zone: ZoneState) => string; tone: string }> = {
  ALIGNED: { label: () => "On · view matches", tone: "green" },
  SHIFTED: { label: (zone) => `On · moved with camera (${zone.shift_pct}%)`, tone: "blue" },
  VIEW_CHANGED: { label: () => "Paused · camera view changed", tone: "red" },
  OUT_OF_VIEW: { label: () => "Paused · out of view", tone: "red" },
  UNVERIFIED: { label: () => "On · not linked to a view", tone: "slate" },
  OTHER_VIEW: { label: () => "Hidden · another view is active", tone: "slate" },
};

const PAUSED_STATES = new Set(["VIEW_CHANGED", "OUT_OF_VIEW"]);

type Live = {
  status: string;
  ai_mode?: string;
  ai_fps?: number;
  inference_ms?: number;
  frames_processed?: number;
  dropped_frames?: number;
  source_state?: string;
  tracks: { track_id: string; class_name: string; confidence: number; hairnet?: string; uniform?: string; checks?: Check[] }[];
  zones?: ZoneState[];
};

export default function CameraDetailPage() {
  const params = useParams<{ id: string }>();
  const [camera, setCamera] = useState<Camera | null>(null);
  const [live, setLive] = useState<Live | null>(null);
  const [frame, setFrame] = useState("");
  const [overlay, setOverlay] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [role, setRole] = useState("");
  const [fpsDraft, setFpsDraft] = useState<string | null>(null);
  useEffect(() => setRole(getUser()?.role || ""), []);
  useEffect(() => {
    if (camera) setFpsDraft(String(camera.ai_fps));
  }, [camera?.id, camera?.ai_fps]);
  const canReview = role === "ADMIN" || role === "SAFETY_MANAGER";
  const admin = role === "ADMIN";

  async function loadFrame(showOverlay: boolean) {
    try {
      const url = await imageUrl(`/api/cameras/${params.id}/snapshot${showOverlay ? "" : "?raw=true"}`);
      setFrame((current) => {
        if (current) URL.revokeObjectURL(current);
        return url;
      });
    } catch {
      setFrame((current) => {
        if (current) URL.revokeObjectURL(current);
        return "";
      });
    }
  }

  useEffect(() => {
    api<Camera>(`/api/cameras/${params.id}`).then(setCamera).catch((err) => setError(err.message));
    const target = Math.min(10, Math.max(1, camera?.ai_fps || 25));
    let frameBusy = false;
    const tickLive = () => {
      api<Live>(`/api/cameras/${params.id}/live`).then(setLive).catch(() => undefined);
    };
    const tickFrame = () => {
      if (frameBusy) return;
      frameBusy = true;
      loadFrame(overlay).finally(() => {
        frameBusy = false;
      });
    };
    tickLive();
    tickFrame();
    const liveTimer = setInterval(tickLive, 1000);
    const frameTimer = setInterval(tickFrame, Math.round(1000 / target));
    return () => {
      clearInterval(liveTimer);
      clearInterval(frameTimer);
    };
    // overlay and the saved FPS are read when this effect restarts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id, overlay, camera?.ai_fps]);

  async function upload(file: File) {
    const body = new FormData();
    body.append("file", file);
    setError("");
    try {
      const updated = await api<Camera>(`/api/cameras/${params.id}/video`, { method: "POST", body });
      setCamera(updated);
      setMessage("Video saved. The worker will loop it as this camera.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function save(partial: Partial<Camera>) {
    setError("");
    try {
      const updated = await api<Camera>(`/api/cameras/${params.id}`, { method: "PATCH", body: JSON.stringify(partial) });
      setCamera(updated);
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save camera settings");
      return null;
    }
  }

  async function commitFps() {
    if (!camera) return;
    const value = Number(fpsDraft);
    if (!Number.isInteger(value) || value < 1 || value > 30) {
      setError("AI FPS must be a whole number from 1 to 30.");
      setFpsDraft(String(camera.ai_fps));
      return;
    }
    if (value === camera.ai_fps) return;
    const updated = await save({ ai_fps: value });
    if (!updated) {
      setFpsDraft(String(camera.ai_fps));
      return;
    }
    setMessage(`AI FPS saved at ${value}. The worker picks it up on the next frame.`);
  }

  const pausedZones = (live?.zones || []).filter((zone) => PAUSED_STATES.has(zone.state));

  return (
    <Shell title={camera?.name || "Camera"}>
      {error ? <div className="mb-3"><ErrorText>{error}</ErrorText></div> : null}
      {message ? <p className="mb-3 text-sm text-pine">{message}</p> : null}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {camera ? <Badge value={STATUS_LABELS[camera.status] || camera.status} tone={statusTone(camera.status)} /> : null}
        <span className="text-sm text-slate-500">{camera?.code} · {camera?.area} · {camera?.ai_fps} FPS</span>
        <Link href={`/cameras/${params.id}/zones`} className="text-sm text-pine">Draw zones</Link>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_320px]">
        <section className="rounded-xl border border-line bg-white p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-medium">Camera view</div>
            <label className="flex items-center gap-2 text-sm"><input className="w-auto" type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} /> Show AI overlay</label>
          </div>
          {pausedZones.length ? (
            <div className="mb-2 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {pausedZones.map((zone) => zone.name).join(", ")} {pausedZones.length === 1 ? "is" : "are"} paused because the camera no longer shows {pausedZones.length === 1 ? "it" : "them"}. Rules there resume when the view matches again, or <Link href={`/cameras/${params.id}/zones`} className="underline">redraw</Link> for the new view.
            </div>
          ) : null}
          {frame ? <img src={frame} alt="Latest camera frame" className="w-full rounded-md bg-stone-200" /> : <div className="grid h-72 place-items-center rounded-md bg-stone-100 text-sm text-slate-500">Waiting for the first frame</div>}
        </section>
        <aside className="space-y-3">
          <section className="rounded-xl border border-line bg-white p-4">
            <h2 className="text-sm font-semibold">People in view</h2>
            <div className="mt-3 space-y-2">
              {(live?.tracks || []).filter((track) => track.class_name === "person").length === 0 ? <p className="text-sm text-slate-500">No person detected on the latest frame.</p> : null}
              {(live?.tracks || []).map((track) => (
                <div key={track.track_id + track.class_name} className="rounded-md bg-paper px-3 py-2 text-sm">
                  <div className="font-medium">{track.class_name === "person" ? `Person ${track.track_id}` : `Forklift ${track.track_id}`}</div>
                  {track.class_name === "person" ? (
                    track.checks?.length ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {track.checks.map((check) => <Badge key={check.text} value={check.text} tone={CHECK_TONES[check.state] || "slate"} />)}
                      </div>
                    ) : (
                      <div className="text-slate-500">Not in a zone with a rule</div>
                    )
                  ) : null}
                  <div className="text-xs text-slate-500">AI confidence {Math.round((track.confidence || 0) * 100)}%</div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-xs text-slate-500">
              Measured {live?.ai_fps ?? 0} FPS · target {camera?.ai_fps ?? "—"} · {Math.round(live?.inference_ms || 0)} ms · {live?.frames_processed ?? 0} frames · {live?.dropped_frames ?? 0} dropped
            </div>
          </section>
          {live?.zones?.length ? (
            <section className="rounded-xl border border-line bg-white p-4">
              <h2 className="text-sm font-semibold">Zones</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {live.zones.map((zone) => {
                  const state = ZONE_STATES[zone.state] || ZONE_STATES.UNVERIFIED;
                  return (
                    <li key={zone.id} className="flex flex-wrap items-center justify-between gap-2">
                      <span>{zone.name}</span>
                      <Badge value={state.label(zone)} tone={state.tone} />
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}
          {admin && camera ? (
            <section className="space-y-2 rounded-xl border border-line bg-white p-4 text-sm">
              <h2 className="font-semibold">Camera settings</h2>
              <label>AI FPS
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={fpsDraft ?? camera.ai_fps}
                  onChange={(e) => setFpsDraft(e.target.value)}
                  onBlur={() => { void commitFps(); }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      e.currentTarget.blur();
                    }
                  }}
                />
              </label>
              <p className="text-xs text-slate-500">1–30. Press Enter or click away to save. Measured FPS is how fast this machine is actually running.</p>
              <label>RTSP or file key<input key={camera.stream_url || "none"} defaultValue={camera.stream_url || ""} onBlur={(e) => { if (e.target.value !== (camera.stream_url || "")) save({ stream_url: e.target.value }); }} /></label>
              <label>Assigned worker<input defaultValue={camera.assigned_worker || ""} placeholder="blank = any worker" onBlur={(e) => save({ assigned_worker: e.target.value || null } as Partial<Camera>)} /></label>
              <label className="flex items-start gap-2">
                <input className="mt-1 w-auto" type="checkbox" checked={Boolean(camera.multi_view)} onChange={(e) => save({ multi_view: e.target.checked })} />
                <span>
                  Camera has several views
                  <span className="block text-xs text-slate-500">For PTZ presets. Zones locked to the same frame form one view; only the view that matches the camera now is shown and checked. Leave off for a fixed camera.</span>
                </span>
              </label>
              <GhostButton type="button" onClick={() => save({ enabled: !camera.enabled })}>{camera.enabled ? "Disable camera" : "Enable camera"}</GhostButton>
              <label className="block">Upload MP4<input className="mt-1" type="file" accept="video/mp4,.mp4" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) upload(file); }} /></label>
            </section>
          ) : null}
          {canReview ? <PrimaryButton onClick={() => api(`/api/cameras/${params.id}/simulate`, { method: "POST" }).then(() => setMessage("Simulation queued. A person will stand inside the zones for a few seconds.")).catch((err) => setError(err.message))}>Simulate an incident</PrimaryButton> : null}
        </aside>
      </div>
    </Shell>
  );
}
