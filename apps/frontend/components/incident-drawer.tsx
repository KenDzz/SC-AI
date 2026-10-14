"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { DangerButton, ErrorText, GhostButton, PrimaryButton, SeverityTag, SEVERITY, Snapshot, StatusPill } from "@/components/ui";
import { api, getUser, Incident } from "@/lib/api";
import { emitIncident } from "@/lib/live";
import { displayFont, eventLabel, formatDate, formatDay, formatTime, shortId, STATUS_LABELS } from "@/lib/labels";

type Feedback = { id: string; decision: string; comment: string; user_name: string; created_at: string };

// Review decisions are one-way (see REVIEW_TRANSITIONS in the backend), so only the moves the server allows are offered.
const ACTIONS: Record<string, { path: string; label: string; result: string; kind: "danger" | "ghost" | "primary" }[]> = {
  NEW: [
    { path: "confirm", label: "Confirm violation", result: "CONFIRMED", kind: "danger" },
    { path: "false-positive", label: "False positive", result: "FALSE_POSITIVE", kind: "ghost" },
  ],
  CONFIRMED: [
    { path: "resolve", label: "Mark resolved", result: "RESOLVED", kind: "primary" },
    { path: "false-positive", label: "False positive", result: "FALSE_POSITIVE", kind: "ghost" },
  ],
};

export default function IncidentDrawer({ id, onClose, onOpen, toast }: { id: string; onClose: () => void; onOpen: (id: string) => void; toast: (message: string, incidentId?: string) => void }) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [lastReview, setLastReview] = useState<Feedback | null>(null);
  const [nextNew, setNextNew] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const canReview = ["ADMIN", "SAFETY_MANAGER"].includes(getUser()?.role || "");

  useEffect(() => {
    setIncident(null);
    setLastReview(null);
    setComment("");
    setError("");
    api<Incident>(`/api/incidents/${id}`).then(setIncident).catch((err) => setError(err.message));
    api<Feedback[]>(`/api/incidents/${id}/feedback`).then((rows) => setLastReview(rows[rows.length - 1] || null)).catch(() => undefined);
    api<{ items: Incident[] }>("/api/incidents?status=NEW&limit=2")
      .then((page) => setNextNew(page.items.find((item) => item.id !== id)?.id || null))
      .catch(() => setNextNew(null));
  }, [id]);

  const closeLatest = useRef(onClose);
  closeLatest.current = onClose;
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeLatest.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function decide(path: string, label: string) {
    setBusy(true);
    setError("");
    try {
      const updated = await api<Incident>(`/api/incidents/${id}/${path}`, { method: "POST", body: JSON.stringify({ comment }) });
      setIncident(updated);
      setComment("");
      api<Feedback[]>(`/api/incidents/${id}/feedback`).then((rows) => setLastReview(rows[rows.length - 1] || null)).catch(() => undefined);
      emitIncident(updated);
      toast(`${shortId(id)} · ${label}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setBusy(false);
    }
  }

  const title = incident ? eventLabel(incident.event_type) : "";
  const actions = incident && canReview ? ACTIONS[incident.status] || [] : [];

  return (
    <>
      <div className="fixed inset-0 z-20 bg-ink/40" onClick={onClose} aria-hidden="true" />
      <div role="dialog" aria-modal="true" aria-labelledby="incident-drawer-title" className="fixed inset-y-0 right-0 z-[21] flex w-[min(460px,100vw)] flex-col overflow-auto bg-surface shadow-[-20px_0_50px_rgba(23,17,12,.25)] motion-safe:animate-slide-in">
        <div className="flex items-center gap-2.5 border-b border-line-muted px-[22px] py-[18px]">
          <span className="flex-1 font-mono text-xs text-bark-400">{shortId(id)}</span>
          <button ref={closeRef} onClick={onClose} aria-label="Close" className="grid h-8 w-8 place-items-center border border-line bg-surface p-0 text-base text-bark-600 hover:bg-paper">×</button>
        </div>
        <div className="relative aspect-[1724/967] shrink-0 overflow-hidden bg-stripes">
          {incident?.snapshot_uri ? (
            <Snapshot path={`/api/incidents/${id}/snapshot`} alt="Evidence snapshot" placeholder="evidence snapshot" className="absolute inset-0 h-full w-full" />
          ) : (
            <div className="grid h-full place-items-center font-mono text-[11.5px] text-husk-500">{incident ? "no snapshot stored" : "loading…"}</div>
          )}
          {incident ? (
            <span className="absolute bottom-3 left-3 px-2 py-1 font-mono text-[10.5px] text-[#FFF7EE]" style={{ background: (SEVERITY[incident.severity] || SEVERITY.LOW).hud }}>
              {title}
              {incident.confidence === null ? "" : ` · ${Math.round(incident.confidence * 100)}%`}
            </span>
          ) : null}
        </div>
        <div className="flex flex-col gap-[18px] px-[22px] py-5">
          {error ? <ErrorText>{error}</ErrorText> : null}
          {incident ? (
            <>
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <SeverityTag severity={incident.severity} />
                  <StatusPill status={incident.status} />
                  {incident.ai_mode === "DEMO" ? <span className="text-xs font-medium text-amber-800">AI Mode: DEMO</span> : null}
                </div>
                <h2 id="incident-drawer-title" className={`text-2xl font-semibold text-bark-900 ${displayFont(title)}`}>{title}</h2>
              </div>
              <dl className="grid grid-cols-[110px_1fr] gap-y-2.5 text-[13.5px]">
                <dt className="text-bark-400">Time</dt>
                <dd className="font-mono text-[13px]">{formatDate(new Date(incident.started_at))}, {formatTime(incident.started_at)}</dd>
                <dt className="text-bark-400">Camera</dt>
                <dd>{incident.camera_name || "—"}</dd>
                <dt className="text-bark-400">Zone</dt>
                <dd>{incident.zone_name || "—"}</dd>
                <dt className="text-bark-400">Rule</dt>
                <dd>{incident.rule_name || "—"}</dd>
                <dt className="text-bark-400">AI confidence</dt>
                <dd>{incident.confidence === null ? "—" : `${Math.round(incident.confidence * 100)}%`}</dd>
              </dl>
              {actions.length ? (
                <>
                  <div className="rounded-[10px] bg-sand px-4 py-3.5 text-[13px] leading-normal text-bark-600">AI raised this alert. Your decision is recorded and feeds the false-positive rate.</div>
                  <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Note for the record (optional)" aria-label="Review note" />
                  <div className="grid grid-cols-2 gap-2.5">
                    {actions.map((action) => {
                      const Button = action.kind === "danger" ? DangerButton : action.kind === "primary" ? PrimaryButton : GhostButton;
                      return (
                        <Button key={action.path} disabled={busy} className="py-3" onClick={() => decide(action.path, STATUS_LABELS[action.result])}>
                          {action.label}
                        </Button>
                      );
                    })}
                  </div>
                </>
              ) : lastReview ? (
                <div className="rounded-[10px] bg-sand px-4 py-3.5 text-[13px] leading-normal text-bark-600">
                  <span className="font-semibold text-bark-800">{STATUS_LABELS[lastReview.decision] || lastReview.decision}</span> by {lastReview.user_name} · {formatDay(lastReview.created_at)} {formatTime(lastReview.created_at)}
                  {lastReview.comment ? <div className="mt-1">“{lastReview.comment}”</div> : null}
                </div>
              ) : !canReview ? (
                <div className="rounded-[10px] bg-sand px-4 py-3.5 text-[13px] text-bark-600">A safety manager reviews this alert.</div>
              ) : null}
              <div className="flex gap-4 text-[13px]">
                <Link href={`/incidents/${id}`} className="link" onClick={onClose}>Full record</Link>
                <div className="flex-1" />
                {nextNew ? <button className="link p-0" onClick={() => onOpen(nextNew)}>Next new incident →</button> : null}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}
