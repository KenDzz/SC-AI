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
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [error, setError] = useState("");
  const [admin, setAdmin] = useState(false);
  useEffect(() => setAdmin(getUser()?.role === "ADMIN"), []);

  function loadZones() {
    api<Zone[]>(`/api/zones?camera_id=${params.id}`).then(setZones).catch((err) => setError(err.message));
  }

  useEffect(() => {
    loadZones();
    imageUrl(`/api/cameras/${params.id}/snapshot?raw=true`)
      .then((url) => {
        const img = new Image();
        img.onload = () => setImage(img);
        img.src = url;
      })
      .catch(() => setImage(null));
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
    const draw = (poly: number[][], color: string, close: boolean) => {
      if (poly.length === 0) return;
      ctx.beginPath();
      poly.forEach(([x, y], index) => {
        const px = x * width;
        const py = y * height;
        if (index === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      if (close) ctx.closePath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      if (close) {
        ctx.fillStyle = color + "33";
        ctx.fill();
      }
      poly.forEach(([x, y]) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x * width, y * height, 4, 0, Math.PI * 2);
        ctx.fill();
      });
    };
    zones.forEach((zone) => draw(zone.polygon, "#1f6b4a", true));
    draw(points, "#b45309", points.length > 2);
  }, [image, zones, points]);

  function addPoint(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!admin) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    setPoints((current) => [...current, [Number(x.toFixed(4)), Number(y.toFixed(4))]]);
  }

  async function save() {
    setError("");
    try {
      await api("/api/zones", { method: "POST", body: JSON.stringify({ camera_id: params.id, name, zone_type: zoneType, polygon: points }) });
      setPoints([]);
      loadZones();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the zone");
    }
  }

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
              <label className="text-sm">Zone name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
              <label className="text-sm">Zone type
                <select value={zoneType} onChange={(e) => setZoneType(e.target.value)}>
                  {TYPES.map((type) => <option key={type} value={type}>{ZONE_LABELS[type]}</option>)}
                </select>
              </label>
              <div className="text-xs text-slate-500">{points.length} points. Click the frame to add corners.</div>
              <div className="flex gap-2">
                <GhostButton type="button" onClick={() => setPoints((current) => current.slice(0, -1))}>Undo</GhostButton>
                <GhostButton type="button" onClick={() => setPoints([])}>Clear</GhostButton>
              </div>
              <PrimaryButton type="button" disabled={points.length < 3} onClick={save}>Save zone</PrimaryButton>
            </div>
          ) : <p className="text-sm text-slate-600">Viewers can see zones. An admin draws them.</p>}
          <div className="rounded-xl border border-line bg-white p-4">
            <h2 className="text-sm font-semibold">Saved zones</h2>
            <ul className="mt-2 space-y-2 text-sm">
              {zones.map((zone) => (
                <li key={zone.id} className="flex items-center justify-between gap-2">
                  <span>{zone.name}<span className="block text-xs text-slate-500">{ZONE_LABELS[zone.zone_type] || zone.zone_type}</span></span>
                  {admin ? <button className="text-xs text-rose-700" onClick={() => api(`/api/zones/${zone.id}`, { method: "DELETE" }).then(loadZones)}>Delete</button> : null}
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
