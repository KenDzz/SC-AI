"use client";

import { FormEvent, useEffect, useState } from "react";
import { useApp } from "@/components/providers";
import Shell from "@/components/shell";
import { ErrorText, SeverityTag, Switch } from "@/components/ui";
import { api, getUser, Rule, Zone } from "@/lib/api";
import { CONDITION_LABELS, eventLabel, ZONE_LABELS } from "@/lib/labels";

const TEMPLATES = [
  { label: "Hairnet required", event_type: "HAIRNET_VIOLATION", condition_type: "HAIRNET_MISSING", severity: "HIGH", min_duration_s: 2 },
  { label: "Uniform required", event_type: "UNIFORM_VIOLATION", condition_type: "UNIFORM_INCORRECT", severity: "HIGH", min_duration_s: 2 },
  { label: "Restricted area", event_type: "RESTRICTED_AREA_INTRUSION", condition_type: "PERSON_INSIDE", severity: "HIGH", min_duration_s: 1 },
  { label: "Machine danger zone", event_type: "MACHINE_DANGER_ZONE_INTRUSION", condition_type: "PERSON_INSIDE", severity: "CRITICAL", min_duration_s: 1 },
  { label: "Forklift lane", event_type: "PEDESTRIAN_IN_FORKLIFT_ZONE", condition_type: "PERSON_INSIDE", severity: "CRITICAL", min_duration_s: 1 },
  { label: "Green bean defect rate", event_type: "GREEN_COFFEE_DEFECT_RATE", condition_type: "DEFECT_RATE", severity: "HIGH", min_duration_s: 2 },
  { label: "Roasted bean defect rate", event_type: "ROASTED_COFFEE_DEFECT_RATE", condition_type: "DEFECT_RATE", severity: "HIGH", min_duration_s: 2 },
];

export default function RulesPage() {
  const { toast } = useApp();
  const [rules, setRules] = useState<Rule[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [template, setTemplate] = useState(TEMPLATES[0].label);
  const [zoneId, setZoneId] = useState("");
  const [name, setName] = useState(TEMPLATES[0].label);
  const [seconds, setSeconds] = useState(2);
  const [cooldown, setCooldown] = useState(30);
  const [error, setError] = useState("");
  const [admin, setAdmin] = useState(false);
  useEffect(() => setAdmin(getUser()?.role === "ADMIN"), []);
  const chosen = TEMPLATES.find((item) => item.label === template) || TEMPLATES[0];

  function load() {
    Promise.all([api<Rule[]>("/api/rules"), api<Zone[]>("/api/zones")])
      .then(([nextRules, nextZones]) => {
        setRules(nextRules);
        setZones(nextZones);
        if (!zoneId && nextZones[0]) setZoneId(nextZones[0].id);
      })
      .catch((err) => setError(err.message));
  }
  useEffect(load, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/rules", {
        method: "POST",
        body: JSON.stringify({
          zone_id: zoneId,
          name,
          event_type: chosen.event_type,
          condition_type: chosen.condition_type,
          min_duration_ms: seconds * 1000,
          cooldown_ms: cooldown * 1000,
          grace_ms: 1000,
          severity: chosen.severity,
          enabled: true,
        }),
      });
      toast(`Rule saved · ${name}`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the rule");
    }
  }

  async function setEnabled(rule: Rule, enabled: boolean) {
    setError("");
    try {
      await api(`/api/rules/${rule.id}`, { method: "PATCH", body: JSON.stringify({ enabled }) });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the rule");
    }
  }

  const label = "flex flex-col gap-1.5 text-[12.5px] text-husk-300";

  return (
    <Shell title="Rules">
      {error ? <ErrorText>{error}</ErrorText> : null}
      <div className="flex flex-wrap items-start gap-5">
        {admin ? (
          <form onSubmit={create} className="panel-dark flex max-w-full flex-[1_1_280px] flex-col gap-3.5 p-[22px]">
            <div className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full bg-rays-soft" aria-hidden="true" />
            <h2 className="relative font-display text-lg font-semibold text-gold-200">New rule</h2>
            <label className={label}>Template
              <select className="field-dark" value={template} onChange={(e) => { setTemplate(e.target.value); setName(e.target.value); const next = TEMPLATES.find((item) => item.label === e.target.value); if (next) setSeconds(next.min_duration_s); }}>
                {TEMPLATES.map((item) => <option key={item.label}>{item.label}</option>)}
              </select>
            </label>
            <label className={label}>Name<input className="field-dark" value={name} onChange={(e) => setName(e.target.value)} required /></label>
            <label className={label}>Zone
              <select className="field-dark" value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} · {ZONE_LABELS[zone.zone_type]}</option>)}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              <label className={label}>Min duration (s)<input className="field-dark" type="number" min={0} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} /></label>
              <label className={label}>Cooldown (s)<input className="field-dark" type="number" min={0} value={cooldown} onChange={(e) => setCooldown(Number(e.target.value))} /></label>
            </div>
            <p className="text-xs leading-normal text-husk-500">
              {CONDITION_LABELS[chosen.condition_type]}.{" "}
              {chosen.condition_type === "DEFECT_RATE"
                ? "Opens when the recent share of defective beans stays above 15%."
                : "Unknown hairnet or uniform results do not raise an alert."}
            </p>
            <button type="submit" className="bg-gold-bar py-3 font-bold text-bark-900 hover:brightness-[1.07]">Save rule</button>
          </form>
        ) : null}
        <div className="panel min-w-0 flex-[999_1_620px] overflow-auto">
          <table className="min-w-[760px]">
            <thead><tr><th>Rule</th><th>Zone</th><th>Violation</th><th>Timing</th><th>Severity</th><th className="text-right">On</th></tr></thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className={rule.enabled ? "" : "opacity-45"}>
                  <td>
                    <div className="text-sm font-semibold">{rule.name}</div>
                    <div className="text-xs text-bark-400">{rule.camera_name}</div>
                  </td>
                  <td className="text-[13.5px]">{rule.zone_name}</td>
                  <td className="text-[13.5px]">{eventLabel(rule.event_type)}</td>
                  <td className="whitespace-nowrap font-mono text-xs text-bark-600">{rule.min_duration_ms / 1000}s · cd {rule.cooldown_ms / 1000}s</td>
                  <td><SeverityTag severity={rule.severity} /></td>
                  <td>
                    <div className="flex justify-end">
                      {admin ? <Switch size="sm" checked={rule.enabled} onChange={(next) => setEnabled(rule, next)} label={`${rule.enabled ? "Disable" : "Enable"} ${rule.name}`} /> : <span className="text-xs text-bark-500">{rule.enabled ? "On" : "Off"}</span>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
