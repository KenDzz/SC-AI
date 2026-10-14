"use client";

import { useEffect, useState } from "react";
import { imageUrl } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/labels";

const TONES: Record<string, string> = {
  slate: "bg-well text-bark-600",
  gold: "bg-gold-100 text-gold-700",
  green: "bg-leaf-50 text-leaf-700",
  red: "bg-crimson-100 text-crimson-700",
  amber: "bg-[#F6E8CD] text-[#7A4F0B]",
  blue: "bg-[#E5ECEE] text-[#3E5A63]",
  orange: "bg-[#F6E8CD] text-[#7A4F0B]",
};

export function Badge({ value, tone = "slate" }: { value: string; tone?: string }) {
  return <span className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${TONES[tone] || TONES.slate}`}>{value}</span>;
}

// Severity: bg/fg for the tag, bar for chart marks, hud for boxes drawn over a camera frame.
export const SEVERITY: Record<string, { tag: string; bar: string; hud: string }> = {
  CRITICAL: { tag: "bg-crimson-100 text-crimson-700", bar: "#9E2A1F", hud: "#D2402F" },
  HIGH: { tag: "bg-[#F6E8CD] text-[#7A4F0B]", bar: "#C99A4A", hud: "#D9A040" },
  MEDIUM: { tag: "bg-[#EFE6D6] text-[#6B5236]", bar: "#A3927F", hud: "#C9A27A" },
  LOW: { tag: "bg-[#E5ECEE] text-[#3E5A63]", bar: "#7E979F", hud: "#7E979F" },
};

export function SeverityTag({ severity }: { severity: string }) {
  const style = SEVERITY[severity] || SEVERITY.LOW;
  return <span className={`inline-flex rounded px-2 py-0.5 text-[10.5px] font-bold tracking-[0.06em] ${style.tag}`}>{severity}</span>;
}

const STATUS_STYLE: Record<string, string> = {
  NEW: "bg-[#FBF1DC] text-gold-700",
  CONFIRMED: "bg-crimson-100 text-crimson-700",
  FALSE_POSITIVE: "bg-[#E6ECE4] text-[#43604B]",
  RESOLVED: "bg-[#E5ECEE] text-[#3E5A63]",
  ONLINE: "bg-leaf-50 text-leaf-700",
  AI_PROCESSING: "bg-leaf-50 text-leaf-700",
  OFFLINE: "bg-well text-husk-700",
  DISABLED: "bg-well text-husk-700",
};

export function StatusPill({ status, label }: { status: string; label?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] || STATUS_STYLE.DISABLED}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {label || STATUS_LABELS[status] || status}
    </span>
  );
}

export function Diamond({ className = "bg-gold-500" }: { className?: string }) {
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 rotate-45 ${className}`} aria-hidden="true" />;
}

// KPI tile. The dark variant leads a row; the crimson accent marks the critical count.
export function Kpi({ label, value, unit, hint, dark = false, accent = "gold" }: { label: string; value: React.ReactNode; unit?: string; hint?: string; dark?: boolean; accent?: "gold" | "crimson" }) {
  const number = dark ? "text-gold-200" : accent === "crimson" ? "text-crimson-700" : "text-bark-900";
  return (
    <div className={`flex min-h-[138px] flex-col gap-2 p-5 ${dark ? "panel-dark" : "panel"}`}>
      {dark ? <div className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-rays" aria-hidden="true" /> : null}
      <div className="flex items-center gap-2">
        <Diamond className={dark ? "bg-gold-300" : accent === "crimson" ? "bg-crimson-600" : "bg-gold-500"} />
        <span className={`text-[12.5px] font-medium ${dark ? "text-husk-300" : "text-bark-500"}`}>{label}</span>
      </div>
      <div className={`font-display text-[40px] font-semibold leading-none ${number}`}>
        {value}
        {unit ? <span className={`text-2xl ${dark ? "text-husk-500" : "text-bark-400"}`}>{unit}</span> : null}
      </div>
      {hint ? <div className={`text-[12.5px] ${dark ? "text-husk-500" : "text-bark-500"}`}>{hint}</div> : null}
    </div>
  );
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border-l-2 border-crimson-600 bg-crimson-50 px-3 py-2 text-sm text-crimson-700">{children}</p>;
}

export function Notice({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border-l-2 border-leaf-600 bg-leaf-50 px-3 py-2 text-sm text-leaf-900">{children}</p>;
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement>;

export function PrimaryButton(props: ButtonProps) {
  return <button {...props} className={`bg-ink px-[18px] py-[11px] font-semibold text-gold-200 hover:bg-ink-soft disabled:opacity-50 ${props.className || ""}`} />;
}

export function OutlineButton(props: ButtonProps) {
  return <button {...props} className={`border border-gold-500 bg-transparent px-[18px] py-[10px] font-semibold text-[#7A520C] hover:bg-gold-100 disabled:opacity-50 ${props.className || ""}`} />;
}

export function GhostButton(props: ButtonProps) {
  return <button {...props} className={`border border-line-strong bg-surface font-semibold text-bark-800 hover:bg-paper disabled:opacity-50 ${props.className || ""}`} />;
}

export function DangerButton(props: ButtonProps) {
  return <button {...props} className={`bg-crimson-600 font-semibold text-[#FFF3EE] hover:bg-crimson-800 disabled:opacity-50 ${props.className || ""}`} />;
}

export function Switch({ checked, onChange, label, size = "md", tone = "leaf", disabled }: { checked: boolean; onChange: (next: boolean) => void; label: string; size?: "md" | "sm"; tone?: "leaf" | "gold"; disabled?: boolean }) {
  const track = size === "md" ? "h-[26px] w-[46px]" : "h-[22px] w-10";
  const knob = size === "md" ? "h-5 w-5" : "h-4 w-4";
  const on = tone === "leaf" ? "bg-leaf-600" : "bg-gold-600";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        event.preventDefault();
        onChange(!checked);
      }}
      className={`flex shrink-0 rounded-full p-[3px] transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${track} ${checked ? `justify-end ${on}` : "justify-start bg-toggle"}`}
    >
      <span className={`rounded-full bg-surface shadow-[0_1px_3px_rgba(0,0,0,.25)] ${knob}`} />
    </button>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: { options: { value: T; label: string }[]; value: T; onChange: (next: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex max-w-full gap-0.5 overflow-x-auto rounded-[9px] bg-well p-[3px]">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`whitespace-nowrap rounded-[7px] px-3.5 py-[7px] text-[13px] font-semibold ${value === option.value ? "bg-surface text-bark-800 shadow-[0_1px_2px_rgba(42,30,21,.14)]" : "text-bark-500 hover:text-bark-800"}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function LiveDot({ demo = false }: { demo?: boolean }) {
  const style = demo ? "bg-amber-500 motion-safe:animate-demo-pulse" : "bg-leaf-600 motion-safe:animate-live-pulse";
  return <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${style}`} aria-hidden="true" />;
}

export function RecDot() {
  return <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-[#E05A4A] motion-safe:animate-rec" aria-hidden="true" />;
}

// An image from the API (it needs the bearer token, so it is fetched as a blob). Striped placeholder until it loads.
export function Snapshot({ path, alt, placeholder, refreshMs, className = "" }: { path: string; alt: string; placeholder: string; refreshMs?: number; className?: string }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let alive = true;
    let current = "";
    const load = () =>
      imageUrl(path)
        .then((url) => {
          if (!alive) return URL.revokeObjectURL(url);
          if (current) URL.revokeObjectURL(current);
          current = url;
          setSrc(url);
        })
        .catch(() => undefined);
    load();
    const timer = refreshMs ? setInterval(load, refreshMs) : undefined;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
      if (current) URL.revokeObjectURL(current);
    };
  }, [path, refreshMs]);
  if (src) return <img src={src} alt={alt} className={`object-cover ${className}`} />;
  return <div className={`grid place-items-center bg-stripes font-mono text-[11.5px] text-husk-500 ${className}`}>{placeholder}</div>;
}

// Gold hairline with a lozenge, the divider the brand uses between headline and copy.
export function Rule({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`} aria-hidden="true">
      <span className="h-px w-11 bg-gold-500" />
      <span className="h-[7px] w-[7px] rotate-45 bg-gold-500" />
      <span className="h-px flex-1 bg-gradient-to-r from-[#D9C7A6] to-transparent" />
    </div>
  );
}

const STAR = Array.from({ length: 28 }, (_, i) => {
  const radius = i % 2 === 0 ? 15 : 6;
  const angle = (Math.PI * i) / 14 - Math.PI / 2;
  return `${(50 + radius * Math.cos(angle)).toFixed(2)},${(50 + radius * Math.sin(angle)).toFixed(2)}`;
}).join(" ");

const TICKS = Array.from({ length: 40 }, (_, i) => {
  const angle = (Math.PI * 2 * i) / 40;
  return [30, 34].map((r) => [50 + r * Math.cos(angle), 50 + r * Math.sin(angle)].map((v) => v.toFixed(2)));
});

// Drawn after the face of a Đông Sơn bronze drum: the star-sun, ringed by bands. Colour comes from currentColor.
export function Emblem({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none" stroke="currentColor" aria-hidden="true">
      <circle cx="50" cy="50" r="47" strokeWidth="2.5" />
      <circle cx="50" cy="50" r="41.5" strokeWidth="1" />
      {[[50, 12.25], [87.75, 50], [50, 87.75], [12.25, 50]].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.8" fill="currentColor" stroke="none" />
      ))}
      <g strokeWidth="1.1">
        {TICKS.map(([[x1, y1], [x2, y2]], i) => <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />)}
      </g>
      <circle cx="50" cy="50" r="26" strokeWidth="1" />
      <circle cx="50" cy="50" r="21" strokeWidth="0.8" strokeDasharray="1.2 2.4" />
      <polygon points={STAR} fill="currentColor" stroke="none" />
    </svg>
  );
}
