"use client";

import { FormEvent, useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, ErrorText, GhostButton, PrimaryButton, severityTone } from "@/components/ui";
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
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the rule");
    }
  }

  return (
    <Shell title="Rules">
      {error ? <div className="mb-3"><ErrorText>{error}</ErrorText></div> : null}
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        {admin ? (
          <form onSubmit={create} className="space-y-3 rounded-xl border border-line bg-white p-4">
            <h2 className="font-semibold">New rule</h2>
            <label className="text-sm">Template
              <select value={template} onChange={(e) => { setTemplate(e.target.value); setName(e.target.value); const next = TEMPLATES.find((item) => item.label === e.target.value); if (next) setSeconds(next.min_duration_s); }}>
                {TEMPLATES.map((item) => <option key={item.label}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-sm">Name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
            <label className="text-sm">Zone
              <select value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} · {ZONE_LABELS[zone.zone_type]}</option>)}
              </select>
            </label>
            <label className="text-sm">Minimum duration (seconds)<input type="number" min={0} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} /></label>
            <label className="text-sm">Cooldown (seconds)<input type="number" min={0} value={cooldown} onChange={(e) => setCooldown(Number(e.target.value))} /></label>
            <p className="text-xs text-slate-500">
              {CONDITION_LABELS[chosen.condition_type]}.{" "}
              {chosen.condition_type === "DEFECT_RATE"
                ? "Opens when the recent share of defective beans stays above 15%."
                : "Unknown hairnet or uniform results do not raise an alert."}
            </p>
            <PrimaryButton type="submit">Save rule</PrimaryButton>
          </form>
        ) : null}
        <div className="overflow-auto rounded-xl border border-line bg-white">
          <table>
            <thead><tr><th>Rule</th><th>Zone</th><th>Violation</th><th>Duration</th><th>Severity</th><th></th></tr></thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id}>
                  <td>{rule.name}<div className="text-xs text-slate-500">{rule.camera_name}</div></td>
                  <td>{rule.zone_name}</td>
                  <td>{eventLabel(rule.event_type)}</td>
                  <td>{rule.min_duration_ms / 1000}s · cooldown {rule.cooldown_ms / 1000}s</td>
                  <td><Badge value={rule.severity} tone={severityTone(rule.severity)} /></td>
                  <td>{admin ? <GhostButton onClick={() => api(`/api/rules/${rule.id}`, { method: rule.enabled ? "PATCH" : "PATCH", body: JSON.stringify({ enabled: !rule.enabled }) }).then(load)}>{rule.enabled ? "Disable" : "Enable"}</GhostButton> : rule.enabled ? "On" : "Off"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
