"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Diamond, ErrorText, Kpi, OutlineButton, SEVERITY } from "@/components/ui";
import { API_URL, api, getToken } from "@/lib/api";
import { eventLabel, percent } from "@/lib/labels";

type Report = {
  incidents: number;
  reviewed: number;
  false_positives: number;
  false_positive_rate: number;
  average_confidence: number | null;
  by_event_type: Record<string, number>;
  by_event_severity: Record<string, string>;
  frames_processed: number;
  dropped_frames: number;
  average_inference_ms: number | null;
  cameras_reporting: number;
  notes: string[];
};

export default function EvaluationPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Report>("/api/system/evaluation").then(setReport).catch((err) => setError(err.message));
  }, []);

  const byType = Object.entries(report?.by_event_type || {}).sort((a, b) => b[1] - a[1]);
  const most = Math.max(1, ...byType.map(([, count]) => count));
  const frames = (report?.frames_processed || 0) + (report?.dropped_frames || 0);
  const processedShare = frames ? (report?.frames_processed || 0) / frames : 0;
  const reviewedShare = report && report.incidents ? Math.round((report.reviewed / report.incidents) * 100) : 0;

  return (
    <Shell
      title="Evaluation"
      actions={<OutlineButton onClick={() => { window.location.href = `${API_URL}/api/system/evaluation?format=csv&access_token=${getToken()}`; }}>Download CSV</OutlineButton>}
    >
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
        <Kpi label="Incidents" value={report?.incidents ?? "—"} hint="Raised by AI in this POC" />
        <Kpi label="Reviewed" value={report?.reviewed ?? "—"} hint={report ? `${reviewedShare}% of all incidents` : undefined} />
        <Kpi label="False positive rate" value={report ? percent(report.false_positive_rate) : "—"} hint="Among reviewed incidents" />
        <Kpi label="Average AI confidence" value={report ? percent(report.average_confidence) : "—"} hint="Across all incidents" />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="panel flex flex-col gap-4 px-6 py-[22px]">
          <h2 className="text-base font-semibold">By violation</h2>
          {byType.length === 0 ? <p className="text-sm text-bark-500">No incidents yet.</p> : null}
          <div className="flex flex-col gap-3">
            {byType.map(([type, count]) => (
              <div key={type} className="grid grid-cols-[minmax(0,180px)_minmax(0,1fr)_34px] items-center gap-3">
                <span className="text-[13.5px]">{eventLabel(type)}</span>
                <span className="h-3 overflow-hidden rounded-[3px] bg-paper">
                  <span className="block h-full rounded-[3px] motion-safe:transition-[width] motion-safe:duration-700" style={{ width: `${(count / most) * 100}%`, background: (SEVERITY[report?.by_event_severity?.[type] || ""] || SEVERITY.HIGH).bar }} />
                </span>
                <span className="text-right font-mono text-[13px]">{count}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="flex flex-col gap-5">
          <section className="panel-dark flex flex-col gap-3.5 px-6 py-[22px]">
            <h2 className="text-base font-semibold text-husk-50">Frame pipeline</h2>
            <div className="flex h-3.5 overflow-hidden rounded bg-[#2B1F15]" role="img" aria-label={`${Math.round(processedShare * 100)}% of frames processed`}>
              <span className="bg-gradient-to-r from-gold-600 to-gold-400" style={{ width: `${processedShare * 100}%` }} />
              {frames ? <span className="flex-1 bg-[repeating-linear-gradient(135deg,#5A2A22_0_5px,#3E1E18_5px_10px)]" /> : null}
            </div>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Processed", String(report?.frames_processed ?? "—"), "text-gold-300", ""],
                ["Dropped", String(report?.dropped_frames ?? "—"), "text-crimson-300", ""],
                ["Inference", report?.average_inference_ms === null || report?.average_inference_ms === undefined ? "—" : String(Math.round(report.average_inference_ms)), "text-husk-50", report?.average_inference_ms === null || report?.average_inference_ms === undefined ? "" : "ms"],
                ["Cameras reporting", String(report?.cameras_reporting ?? "—"), "text-husk-50", ""],
              ].map(([label, value, color, unit]) => (
                <div key={label} className="flex flex-col gap-0.5">
                  <dt className="text-[11.5px] text-husk-500">{label}</dt>
                  <dd className={`font-display text-2xl font-semibold ${color}`}>
                    {value}
                    {unit ? <span className="ml-1 font-sans text-sm font-medium text-husk-300">{unit}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="text-[12.5px] leading-normal text-husk-500">
              {!frames
                ? "No camera has reported frames yet."
                : processedShare < 0.5
                  ? `${Math.round((1 - processedShare) * 100)}% of frames are dropped before inference — check the sampling rate before reading alert numbers.`
                  : `${Math.round(processedShare * 100)}% of frames reach inference.`}
            </p>
          </section>
          <section className="panel flex flex-col gap-2.5 px-6 py-5">
            <h2 className="text-sm font-semibold">How to read these numbers</h2>
            {(report?.notes || []).map((note) => (
              <p key={note} className="flex items-baseline gap-2.5 text-[13px] leading-normal text-bark-600">
                <Diamond className="relative -top-px bg-gold-500" />
                {note}
              </p>
            ))}
          </section>
        </div>
      </div>
    </Shell>
  );
}
