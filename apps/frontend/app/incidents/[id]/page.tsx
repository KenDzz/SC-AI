"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { DangerButton, ErrorText, GhostButton, PrimaryButton, SeverityTag, Snapshot, StatusPill } from "@/components/ui";
import { api, getUser, Incident } from "@/lib/api";
import { emitIncident, useIncidentEvents } from "@/lib/live";
import { eventLabel, formatWhen, shortId, STATUS_LABELS } from "@/lib/labels";

type Feedback = { id: string; decision: string; comment: string; user_name: string; created_at: string };

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [canReview, setCanReview] = useState(false);
  useEffect(() => setCanReview(["ADMIN", "SAFETY_MANAGER"].includes(getUser()?.role || "")), []);

  function load() {
    api<Incident>(`/api/incidents/${params.id}`).then(setIncident).catch((err) => setError(err.message));
    api<Feedback[]>(`/api/incidents/${params.id}/feedback`).then(setFeedback).catch(() => undefined);
  }
  useEffect(load, [params.id]);
  useIncidentEvents((changed) => {
    if (!changed || changed.id === params.id) load();
  }, 500);

  async function review(path: string) {
    setError("");
    try {
      const updated = await api<Incident>(`/api/incidents/${params.id}/${path}`, { method: "POST", body: JSON.stringify({ comment }) });
      setComment("");
      emitIncident(updated);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    }
  }

  const open = incident && ["NEW", "CONFIRMED"].includes(incident.status);

  return (
    <Shell title={incident ? eventLabel(incident.event_type) : "Incident"} back={{ href: "/incidents", label: "Incidents" }}>
      {error ? <ErrorText>{error}</ErrorText> : null}
      {incident ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="panel overflow-hidden">
            <div className="relative aspect-video bg-stripes">
              {incident.snapshot_uri ? (
                <Snapshot path={`/api/incidents/${params.id}/snapshot`} alt="Incident snapshot" placeholder="evidence snapshot" className="absolute inset-0 h-full w-full" />
              ) : (
                <div className="grid h-full place-items-center font-mono text-xs text-husk-500">No snapshot was stored for this incident.</div>
              )}
            </div>
            <p className="px-4 py-3 text-xs text-bark-500">
              {incident.clip_uri ? `Clip: ${incident.clip_uri}` : "Video clips can be added later without changing this record. This incident stores a snapshot."}
            </p>
          </section>
          <section className="panel flex flex-col gap-4 p-5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-bark-400">{shortId(incident.id)}</span>
              <SeverityTag severity={incident.severity} />
              <StatusPill status={incident.status} />
              {incident.ai_mode ? <span className={`text-xs font-medium ${incident.ai_mode === "DEMO" ? "text-amber-800" : "text-leaf-700"}`}>AI Mode: {incident.ai_mode}</span> : null}
            </div>
            <dl className="grid grid-cols-[110px_1fr] gap-y-2.5 text-[13.5px]">
              {[
                ["Camera", incident.camera_name || "—"],
                ["Zone", incident.zone_name || "—"],
                ["Rule", incident.rule_name || "—"],
                ["AI confidence", incident.confidence === null ? "—" : `${Math.round(incident.confidence * 100)}%`],
                ["Model", `${incident.model_name || "—"} ${incident.model_version || ""}`],
                ["Started", formatWhen(incident.started_at)],
                ["Ended", formatWhen(incident.ended_at)],
                ["Track", incident.track_id || "—"],
              ].map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-bark-400">{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            {canReview && open ? (
              <div className="flex flex-col gap-2.5 border-t border-line-soft pt-4">
                <textarea rows={3} placeholder="Note for the record (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
                <div className="flex flex-wrap gap-2">
                  {incident.status === "NEW" ? <DangerButton onClick={() => review("confirm")}>Confirm violation</DangerButton> : null}
                  <GhostButton onClick={() => review("false-positive")}>False positive</GhostButton>
                  <PrimaryButton onClick={() => review("resolve")}>Mark resolved</PrimaryButton>
                </div>
              </div>
            ) : null}
            <div className="border-t border-line-soft pt-4">
              <h2 className="font-semibold">Review history</h2>
              <ul className="mt-2 space-y-2">
                {feedback.map((item) => (
                  <li key={item.id} className="rounded-lg bg-sand px-3 py-2">
                    <div className="font-medium">{STATUS_LABELS[item.decision] || item.decision} · {item.user_name}</div>
                    <div className="font-mono text-xs text-bark-400">{formatWhen(item.created_at)}</div>
                    {item.comment ? <div className="mt-1">{item.comment}</div> : null}
                  </li>
                ))}
                {feedback.length === 0 ? <li className="text-bark-500">No review yet.</li> : null}
              </ul>
            </div>
          </section>
        </div>
      ) : null}
    </Shell>
  );
}
