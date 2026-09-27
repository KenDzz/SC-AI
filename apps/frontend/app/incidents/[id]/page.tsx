"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, ErrorText, GhostButton, PrimaryButton, severityTone, statusTone } from "@/components/ui";
import { api, getUser, imageUrl, Incident } from "@/lib/api";
import { eventLabel, formatWhen, STATUS_LABELS } from "@/lib/labels";

type Feedback = { id: string; decision: string; comment: string; user_name: string; created_at: string };

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [shot, setShot] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [canReview, setCanReview] = useState(false);
  useEffect(() => setCanReview(["ADMIN", "SAFETY_MANAGER"].includes(getUser()?.role || "")), []);

  function load() {
    api<Incident>(`/api/incidents/${params.id}`).then(setIncident).catch((err) => setError(err.message));
    api<Feedback[]>(`/api/incidents/${params.id}/feedback`).then(setFeedback).catch(() => undefined);
    imageUrl(`/api/incidents/${params.id}/snapshot`).then(setShot).catch(() => setShot(""));
  }
  useEffect(load, [params.id]);

  async function review(path: string) {
    setError("");
    try {
      await api(`/api/incidents/${params.id}/${path}`, { method: "POST", body: JSON.stringify({ comment }) });
      setComment("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    }
  }

  const open = incident && ["NEW", "CONFIRMED"].includes(incident.status);

  return (
    <Shell title="Incident">
      <Link href="/incidents" className="text-sm text-pine">Back to incidents</Link>
      {error ? <div className="my-3"><ErrorText>{error}</ErrorText></div> : null}
      {incident ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="rounded-xl border border-line bg-white p-3">
            {shot ? <img src={shot} alt="Incident snapshot" className="w-full rounded-md" /> : <div className="grid h-72 place-items-center text-sm text-slate-500">No snapshot was stored for this incident.</div>}
            {incident.clip_uri ? <p className="mt-2 text-sm">Clip: {incident.clip_uri}</p> : <p className="mt-2 text-xs text-slate-500">Video clips can be added later without changing this record. This incident stores a snapshot.</p>}
          </section>
          <section className="space-y-3 rounded-xl border border-line bg-white p-4 text-sm">
            <div className="flex flex-wrap gap-2">
              <Badge value={eventLabel(incident.event_type)} tone="slate" />
              <Badge value={incident.severity} tone={severityTone(incident.severity)} />
              <Badge value={STATUS_LABELS[incident.status] || incident.status} tone={statusTone(incident.status)} />
              {incident.ai_mode ? <Badge value={`AI Mode: ${incident.ai_mode}`} tone={incident.ai_mode === "DEMO" ? "amber" : "green"} /> : null}
            </div>
            <Field label="Camera" value={incident.camera_name || ""} />
            <Field label="Zone" value={incident.zone_name || "—"} />
            <Field label="Rule" value={incident.rule_name || "—"} />
            <Field label="AI confidence" value={incident.confidence === null ? "—" : `${Math.round(incident.confidence * 100)}%`} />
            <Field label="Model" value={`${incident.model_name || "—"} ${incident.model_version || ""}`} />
            <Field label="Started" value={formatWhen(incident.started_at)} />
            <Field label="Ended" value={formatWhen(incident.ended_at)} />
            <Field label="Track" value={incident.track_id || "—"} />
            {canReview && open ? (
              <div className="space-y-2 pt-2">
                <textarea rows={3} placeholder="Comment" value={comment} onChange={(e) => setComment(e.target.value)} />
                <div className="flex flex-wrap gap-2">
                  {incident.status === "NEW" ? <PrimaryButton onClick={() => review("confirm")}>Confirm</PrimaryButton> : null}
                  <GhostButton onClick={() => review("false-positive")}>False positive</GhostButton>
                  <GhostButton onClick={() => review("resolve")}>Resolve</GhostButton>
                </div>
              </div>
            ) : null}
            <div>
              <h2 className="font-semibold">Review history</h2>
              <ul className="mt-2 space-y-2">
                {feedback.map((item) => (
                  <li key={item.id} className="rounded-md bg-paper px-3 py-2">
                    <div className="font-medium">{STATUS_LABELS[item.decision] || item.decision} · {item.user_name}</div>
                    <div className="text-xs text-slate-500">{formatWhen(item.created_at)}</div>
                    {item.comment ? <div className="mt-1">{item.comment}</div> : null}
                  </li>
                ))}
                {feedback.length === 0 ? <li className="text-slate-500">No review yet.</li> : null}
              </ul>
            </div>
          </section>
        </div>
      ) : null}
    </Shell>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return <div><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div>{value}</div></div>;
}
