export function Badge({ value, tone = "slate" }: { value: string; tone?: string }) {
  const tones: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-100 text-emerald-800",
    red: "bg-rose-100 text-rose-800",
    amber: "bg-amber-100 text-amber-900",
    blue: "bg-sky-100 text-sky-800",
    orange: "bg-orange-100 text-orange-900",
  };
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${tones[tone] || tones.slate}`}>{value}</span>;
}

export function severityTone(severity: string) {
  if (severity === "CRITICAL") return "red";
  if (severity === "HIGH") return "orange";
  if (severity === "MEDIUM") return "amber";
  return "blue";
}

export function statusTone(status: string) {
  if (status === "CONFIRMED" || status === "AI_PROCESSING" || status === "ONLINE") return "green";
  if (status === "FALSE_POSITIVE" || status === "OFFLINE") return "amber";
  if (status === "NEW" || status === "CRITICAL") return "red";
  if (status === "RESOLVED") return "blue";
  return "slate";
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-white p-4 shadow-sm ${className}`}>{children}</section>;
}

export function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Card>
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-ink">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
    </Card>
  );
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800">{children}</p>;
}

export function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} className={`bg-pine text-white hover:bg-emerald-800 disabled:opacity-50 ${props.className || ""}`} />;
}

export function GhostButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} className={`border border-line bg-white text-ink hover:bg-stone-50 disabled:opacity-50 ${props.className || ""}`} />;
}
