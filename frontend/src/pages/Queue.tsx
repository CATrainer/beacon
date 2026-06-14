import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Lane, LeadListResponse, LeadStage } from "../types";

const STAGES: LeadStage[] = ["sourced", "qualified", "scored", "enriched", "ready", "rejected"];

function scoreBadge(score: number | null) {
  if (score == null) return <span className="text-slate-400">—</span>;
  const tone =
    score >= 70 ? "bg-green-100 text-green-800" : score >= 40 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600";
  return <span className={`badge ${tone}`}>{Math.round(score)}</span>;
}

export function Queue() {
  const navigate = useNavigate();
  const [laneId, setLaneId] = useState<string>("");
  const [stage, setStage] = useState<string>("");
  const [q, setQ] = useState("");
  const [minScore, setMinScore] = useState<string>("");

  const { data: lanes } = useQuery({
    queryKey: ["lanes"],
    queryFn: () => api.get<Lane[]>("/api/lanes"),
  });

  const params = new URLSearchParams();
  if (laneId) params.set("lane_id", laneId);
  if (stage) params.set("stage", stage);
  if (q.trim()) params.set("q", q.trim());
  if (minScore) params.set("min_score", minScore);

  const { data, isLoading } = useQuery({
    queryKey: ["leads", laneId, stage, q, minScore],
    queryFn: () => api.get<LeadListResponse>(`/api/leads?${params.toString()}`),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">Ranked queue</h1>
          <p className="text-sm text-slate-500">
            Leads sorted by final score. Sourcing that fills this queue arrives in the next slice.
          </p>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select className="input w-44" value={laneId} onChange={(e) => setLaneId(e.target.value)}>
          <option value="">All lanes</option>
          {lanes?.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
        <select className="input w-44" value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          className="input w-64"
          placeholder="Search company or domain…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <input
          type="number"
          min={0}
          max={100}
          className="input w-32"
          placeholder="Min score"
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-line bg-canvas text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Company</th>
              <th className="px-3 py-2">Location</th>
              <th className="px-3 py-2">Stage</th>
              <th className="px-3 py-2 text-center">Fit</th>
              <th className="px-3 py-2 text-center">Gap</th>
              <th className="px-3 py-2 text-center">Reach</th>
              <th className="px-3 py-2 text-center">Final</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && (data?.items.length ?? 0) === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-10 text-center text-slate-400">
                  No leads yet. Configure a lane and run a source (coming in Slice 2) to populate
                  the queue.
                </td>
              </tr>
            )}
            {data?.items.map((lead) => (
              <tr
                key={lead.id}
                onClick={() => navigate(`/leads/${lead.id}`)}
                className="cursor-pointer border-b border-line last:border-0 hover:bg-canvas"
              >
                <td className="px-3 py-2">
                  <div className="font-medium">{lead.company}</div>
                  {lead.domain && <div className="text-xs text-slate-400">{lead.domain}</div>}
                  {lead.reject_reason && (
                    <div className="text-xs text-red-600">{lead.reject_reason}</div>
                  )}
                </td>
                <td className="px-3 py-2 text-slate-600">{lead.location ?? "—"}</td>
                <td className="px-3 py-2">
                  <span className="badge bg-canvas text-slate-600">{lead.stage}</span>
                </td>
                <td className="px-3 py-2 text-center">{scoreBadge(lead.fit_score)}</td>
                <td className="px-3 py-2 text-center">{scoreBadge(lead.gap_score)}</td>
                <td className="px-3 py-2 text-center">{scoreBadge(lead.reachability_score)}</td>
                <td className="px-3 py-2 text-center font-semibold">
                  {scoreBadge(lead.final_score)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && data.total > 0 && (
        <p className="mt-2 text-xs text-slate-400">{data.total} leads</p>
      )}
    </div>
  );
}
