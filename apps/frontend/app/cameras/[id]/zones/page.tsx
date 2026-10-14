"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Shell from "@/components/shell";
import { ErrorText, GhostButton, PrimaryButton } from "@/components/ui";
import { api, getUser, imageUrl, Zone } from "@/lib/api";
import { ZONE_LABELS } from "@/lib/labels";

const TYPES = Object.keys(ZONE_LABELS);

export default function ZonesPage() {
  const params = useParams<{ id: string }>();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [points, setPoints] = useState<number[][]>([]);
  const [name, setName] = useState("Restricted Zone");
  const [zoneType, setZoneType] = useState("RESTRICTED_AREA");
  const [editing, setEditing] = useState<Zone | null>(null);
  const [referenceId, setReferenceId] = useState<string | null>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [error, setError] = useState("");
  const [admin, setAdmin] = useState(false);
  useEffect(() => setAdmin(getUser()?.role === "ADMIN"), []);

  function loadZones() {
    api<Zone[]>(`/api/zones?camera_id=${params.id}`).then(setZones).catch((err) => setError(err.message));
  }

  useEffect(() => {
    loadZones();
    const show = (url: string) => {
      const img = new Image();
      img.onload = () => setImage(img);
      img.src = url;
    };
    const showLatest = () => imageUrl(`/api/cameras/${params.id}/snapshot?raw=true`).then(show).catch(() => setImage(null));
    if (getUser()?.role !== "ADMIN") {
      showLatest();
      return;
    }
    // Freeze the frame an admin draws on, so saved zones can follow the camera if it moves later.
    api<{ id: string }>(`/api/cameras/${params.id}/reference-frames`, { method: "POST" })
      .then(({ id }) => {
        setReferenceId(id);
        return imageUrl(`/api/cameras/${params.id}/reference-frames/${id}`).then(show);
      })
      .catch(() => {
        setReferenceId(null);
        showLatest();
      });
  }, [params.id]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const width = 960;
    const height = 540;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);
    if (image) ctx.drawImage(image, 0, 0, width, height);
    else {
      ctx.fillStyle = "#e7e2d8";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#64748b";
      ctx.fillText("Waiting for a camera frame", 24, 32);
    }
    const draw = (poly: number[][], color: string, close: boolean, options: { dashed?: boolean; label?: string } = {}) => {
      if (poly.length === 0) return;
      ctx.beginPath();
      poly.forEach(([x, y], index) => {
        const px = x * width;
        const py = y * height;
        if (index === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      if (close) ctx.closePath();
      ctx.setLineDash(options.dashed ? [8, 6] : []);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.setLineDash([]);
      if (close && !options.dashed) {
        ctx.fillStyle = color + "33";
        ctx.fill();
      }
      if (!options.dashed) {
        poly.forEach(([x, y]) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(x * width, y * height, 4, 0, Math.PI * 2);
          ctx.fill();
        });
      }
      if (options.label) {
        const [x, y] = poly[0];
        ctx.font = "13px Segoe UI, Arial, sans-serif";
        const textWidth = ctx.measureText(options.label).width;
        const top = Math.max(0, y * height - 24);
        ctx.fillStyle = color;
        ctx.fillRect(x * width, top, textWidth + 10, 20);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(options.label, x * width + 5, top + 14);
      }
    };
    zones.forEach((zone) => {
      if (zone.id === editing?.id) draw(zone.polygon, "#64748b", true, { dashed: true, label: `${zone.name} (current)` });
      else draw(zone.polygon, "#1f6b4a", true, { label: zone.name });
    });
    draw(points, "#b45309", points.length > 2);
  }, [image, zones, points, editing]);

  function addPoint(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!admin) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    setPoints((current) => [...current, [Number(x.toFixed(4)), Number(y.toFixed(4))]]);
  }

  function startRedraw(zone: Zone) {
    setError("");
    setEditing(zone);
    setName(zone.name);
    setZoneType(zone.zone_type);
    setPoints([]);
  }

  function stopRedraw() {
    setEditing(null);
    setName("Restricted Zone");
    setZoneType("RESTRICTED_AREA");
    setPoints([]);
  }

  async function save() {
    setError("");
    try {
      const reference = referenceId ? { reference_id: referenceId } : {};
      if (editing) {
        await api(`/api/zones/${editing.id}`, { method: "PATCH", body: JSON.stringify({ name, polygon: points, ...reference }) });
        stopRedraw();
      } else {
        await api("/api/zones", { method: "POST", body: JSON.stringify({ camera_id: params.id, name, zone_type: zoneType, polygon: points, ...reference }) });
        setPoints([]);
      }
      loadZones();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the zone");
    }
  }

  async function lockToView(zone: Zone) {
    setError("");
    try {
      await api(`/api/zones/${zone.id}`, { method: "PATCH", body: JSON.stringify({ reference_id: referenceId }) });
      loadZones();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not lock the zone to this view");
    }
  }

  // Zones locked to the same frame belong to one view; number the views in list order.
  const viewNumbers = new Map<string, number>();
  zones.forEach((zone) => {
    if (zone.reference_key && !viewNumbers.has(zone.reference_key)) viewNumbers.set(zone.reference_key, viewNumbers.size + 1);
  });

  return (
    <Shell title="Zone configuration">
      <div className="mb-3 flex items-center justify-between">
        <Link href={`/cameras/${params.id}`} className="text-sm text-pine">Back to camera</Link>
        <span className="text-sm text-slate-500">Points are saved as fractions of the frame, from 0 to 1.</span>
      </div>
      {error ? <div className="mb-3"><ErrorText>{error}</ErrorText></div> : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <canvas ref={canvasRef} onClick={addPoint} className="w-full cursor-crosshair rounded-xl border border-line bg-white" />
        <div className="space-y-3">
          {admin ? (
            <div className="space-y-2 rounded-xl border border-line bg-white p-4">
              <h2 className="text-sm font-semibold">{editing ? `Redraw ${editing.name}` : "New zone"}</h2>
              <label className="text-sm">Zone name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
              <label className="text-sm">Zone type
                <select value={zoneType} onChange={(e) => setZoneType(e.target.value)} disabled={Boolean(editing)}>
                  {TYPES.map((type) => <option key={type} value={type}>{ZONE_LABELS[type]}</option>)}
                </select>
              </label>
              {zoneType === "GREEN_COFFEE_LINE" || zoneType === "ROASTED_COFFEE_LINE" || zoneType === "COFFEE_COUNT_LINE" ? (
                <p className="text-xs text-slate-500">Draw the belt. Each bean is counted once when it crosses the horizontal middle, moving down the frame. Green and roasted belts also grade defects. The count belt only totals quantity.</p>
              ) : null}
              <div className="text-xs text-slate-500">
                {points.length} points. Click the corners in order around the area. Any number of corners works.
                {editing ? " The dashed outline is the current shape. Its rules and past incidents stay linked." : ""}
              </div>
              <div className="text-xs text-slate-500">
                {referenceId
                  ? "Zones saved here remember this frame. If the camera moves a little they follow it; if the view changes too much they pause."
                  : "No camera frame to remember yet. Zones saved now stay where they are drawn even if the camera moves."}
              </div>
              <div className="flex gap-2">
                <GhostButton type="button" onClick={() => setPoints((current) => current.slice(0, -1))}>Undo</GhostButton>
                <GhostButton type="button" onClick={() => setPoints([])}>Clear</GhostButton>
              </div>
              <div className="flex gap-2">
                <PrimaryButton type="button" disabled={points.length < 3} onClick={save}>{editing ? "Save new shape" : "Save zone"}</PrimaryButton>
                {editing ? <GhostButton type="button" onClick={stopRedraw}>Cancel</GhostButton> : null}
              </div>
            </div>
          ) : <p className="text-sm text-slate-600">Viewers can see zones. An admin draws them.</p>}
          <div className="rounded-xl border border-line bg-white p-4">
            <h2 className="text-sm font-semibold">Saved zones</h2>
            <ul className="mt-2 space-y-2 text-sm">
              {zones.map((zone) => (
                <li key={zone.id} className={`flex items-center justify-between gap-2 ${zone.id === editing?.id ? "rounded-md bg-amber-50 px-2 py-1" : ""}`}>
                  <span>
                    {zone.name}
                    <span className="block text-xs text-slate-500">{ZONE_LABELS[zone.zone_type] || zone.zone_type} · {zone.polygon.length} corners</span>
                    <span className="block text-xs text-slate-500">{zone.reference_key ? `Follows camera moves · View ${viewNumbers.get(zone.reference_key)}` : "Not linked to a camera view"}</span>
                  </span>
                  {admin ? (
                    <span className="flex flex-wrap justify-end gap-x-3">
                      <button className="text-xs text-pine" onClick={() => startRedraw(zone)}>Redraw</button>
                      {referenceId ? (
                        <button className="text-xs text-pine" title="Use when the zone already matches this frame. Zones locked together form one view." onClick={() => lockToView(zone)}>Lock to this view</button>
                      ) : null}
                      <button className="text-xs text-rose-700" onClick={() => api(`/api/zones/${zone.id}`, { method: "DELETE" }).then(() => { if (zone.id === editing?.id) stopRedraw(); loadZones(); })}>Delete</button>
                    </span>
                  ) : null}
                </li>
              ))}
              {zones.length === 0 ? <li className="text-slate-500">No zones yet.</li> : null}
            </ul>
          </div>
        </div>
      </div>
    </Shell>
  );
}
