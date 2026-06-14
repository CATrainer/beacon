import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Pipeline as PipelineData } from "../types";

// CRM pipeline order (§7).
const STAGES: { key: string; label: string }[] = [
  { key: "sourced", label: "Sourced" },
  { key: "qualified", label: "Qualified" },
  { key: "researched", label: "Researched" },
  { key: "prepped", label: "Prepped" },
  { key: "queued", label: "Queued" },
  { key: "sent", label: "Sent" },
  { key: "replied", label: "Replied" },
  { key: "call_booked", label: "Call booked" },
  { key: "audit_sold", label: "Audit sold" },
  { key: "delivered", label: "Delivered" },
  { key: "retainer", label: "Retainer" },
  { key: "lost", label: "Lost" },
];

export function Pipeline() {
  const { data } = useQuery({
    queryKey: ["pipeline"],
    queryFn: () => api.get<PipelineData>("/api/pipeline"),
  });
  const counts = data?.counts ?? {};

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-bold">Pipeline</h1>
        <p className="text-sm text-slate-500">
          The CRM — every lead's place in the funnel. This replaces HubSpot.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        {STAGES.map((s) => (
          <Link
            key={s.key}
            to={`/queue?status=${s.key}`}
            className="card p-4 transition-colors hover:bg-canvas"
          >
            <div className="text-2xl font-bold">{counts[s.key] ?? 0}</div>
            <div className="text-sm text-slate-500">{s.label}</div>
          </Link>
        ))}
      </div>
      <div className="mt-4 flex gap-4 text-xs text-slate-400">
        <span>Rejected: {counts["rejected"] ?? 0}</span>
        <span>Suppressed: {counts["suppressed"] ?? 0}</span>
      </div>
    </div>
  );
}
