import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import type { CostEstimate, IntegrationStatus, Job } from "../types";
import { JobProgress } from "./JobProgress";

/** Run the Stage-4b GEO gap pre-check on a lane's top-N leads (triage only, §4b). */
export function GeoCheckLane({ laneId }: { laneId: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [topN, setTopN] = useState(25);
  const [fixtures, setFixtures] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: status } = useQuery({
    queryKey: ["status"],
    queryFn: () => api.get<IntegrationStatus>("/api/status"),
  });
  const noEngines = (status?.geo_engines.length ?? 0) === 0;

  const { data: estimate } = useQuery({
    queryKey: ["geo-estimate", laneId, topN],
    queryFn: () => api.get<CostEstimate>(`/api/lanes/${laneId}/geo/estimate?top_n=${topN}`),
    enabled: open,
  });

  const run = useMutation({
    mutationFn: () =>
      api.post<Job>(`/api/lanes/${laneId}/geo`, {
        top_n: topN,
        force_fixtures: fixtures || noEngines,
      }),
    onSuccess: (job) => {
      setJobId(job.id);
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed to start"),
  });

  if (!open) {
    return (
      <button className="btn-ghost" onClick={() => setOpen(true)}>
        GEO check
      </button>
    );
  }

  return (
    <div className="mt-2 w-full rounded-md border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          <span className="label">Top N by score</span>
          <input
            type="number"
            min={1}
            max={500}
            className="input w-24"
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={fixtures || noEngines}
            disabled={noEngines}
            onChange={(e) => setFixtures(e.target.checked)}
          />
          Use fixtures
        </label>
        {estimate && (
          <span className="text-xs text-slate-500">
            {estimate.lead_count} leads · est. <b>${estimate.estimated_usd.toFixed(2)}</b>
          </span>
        )}
        <button className="btn-primary" disabled={run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? "Starting…" : "Run GEO check"}
        </button>
        <button className="btn-ghost" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      {noEngines && (
        <p className="mt-2 text-xs text-amber-700">
          No GEO engine keys configured — running with fixtures. Add a Perplexity/OpenAI/Gemini
          key for real results.
        </p>
      )}
      <p className="mt-2 text-xs text-slate-400">
        Triage for ranking & hook detection only — not the deliverable audit. Real evidence is the
        screenshots you capture in prep.
      </p>
      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
      {jobId && (
        <JobProgress
          jobId={jobId}
          onDone={() => qc.invalidateQueries({ queryKey: ["leads"] })}
        />
      )}
    </div>
  );
}
