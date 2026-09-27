"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/labels";

type ModelRow = { id: string; name: string; version: string; model_type: string; status: string; description: string; created_at: string };

export default function ModelsPage() {
  const [rows, setRows] = useState<ModelRow[]>([]);
  useEffect(() => {
    api<ModelRow[]>("/api/models").then(setRows);
  }, []);
  return (
    <Shell title="AI models">
      <p className="mb-4 max-w-3xl text-sm text-slate-600">The worker calls a detector and a PPE classifier through adapters. DEMO mode does not need weight files. REAL mode uses the built-in person detector, or ONNX files placed in the model folder.</p>
      <div className="overflow-auto rounded-xl border border-line bg-white">
        <table>
          <thead><tr><th>Model</th><th>Version</th><th>Type</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name}<div className="max-w-xl text-xs text-slate-500">{row.description}</div></td>
                <td>{row.version}</td>
                <td>{row.model_type}</td>
                <td><Badge value={row.status} tone={statusTone(row.status === "ACTIVE" ? "ONLINE" : "OFFLINE")} /></td>
                <td>{formatWhen(row.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
