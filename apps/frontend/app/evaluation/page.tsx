"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Stat } from "@/components/ui";
import { API_URL, api, getToken } from "@/lib/api";
import { eventLabel, percent } from "@/lib/labels";

type Report = {
  incidents: number;
  reviewed: number;
  false_positives: number;
  false_positive_rate: number;
  average_confidence: number | null;
  by_event_type: Record<string, number>;
  frames_processed: number;
  dropped_frames: number;
  average_inference_ms: number | null;
  cameras_reporting: number;
  notes: string[];
};

export default function EvaluationPage() {
  const [report, setReport] = useState<Report | null>(null);
  useEffect(() => {
    api<Report>("/api/system/evaluation").then(setReport);
  }, []);
  return (
    <Shell title="Evaluation">
      <div className="grid gap-3 md:grid-cols-4">
        <Stat label="Incidents" value={report?.incidents ?? "—"} />
        <Stat label="Reviewed" value={report?.reviewed ?? "—"} />
        <Stat label="False positive rate" value={report ? percent(report.false_positive_rate) : "—"} />
        <Stat label="Average AI confidence" value={report?.average_confidence === null || report?.average_confidence === undefined ? "—" : percent(report.average_confidence)} />
        <Stat label="Frames processed" value={report?.frames_processed ?? "—"} />
        <Stat label="Dropped frames" value={report?.dropped_frames ?? "—"} />
        <Stat label="Inference" value={report?.average_inference_ms === null || report?.average_inference_ms === undefined ? "—" : `${report.average_inference_ms} ms`} />
        <Stat label="Cameras reporting" value={report?.cameras_reporting ?? "—"} />
      </div>
      <section className="mt-4 rounded-xl border border-line bg-white p-4">
        <h2 className="font-semibold">By violation</h2>
        <ul className="mt-2 text-sm">
          {Object.entries(report?.by_event_type || {}).map(([key, count]) => <li key={key}>{eventLabel(key)}: {count}</li>)}
        </ul>
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-slate-600">
          {(report?.notes || []).map((note) => <li key={note}>{note}</li>)}
        </ul>
        <button className="mt-4 text-sm text-pine" onClick={() => { window.location.href = `${API_URL}/api/system/evaluation?format=csv&access_token=${getToken()}`; }}>Download CSV</button>
      </section>
    </Shell>
  );
}
