import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import type { CostEstimate, Job } from "../types";
import { JobProgress } from "./JobProgress";

/** Run Stage-4 research on the top-N leads of a lane, with a cost estimate (§9). */
export function ResearchLane({ laneId }: { laneId: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [topN, setTopN] = useState(25);
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: estimate } = useQuery({
    queryKey: ["research-estimate", laneId, topN],
    queryFn: () =>
      api.get<CostEstimate>(`/api/lanes/${laneId}/research/estimate?top_n=${topN}`),
    enabled: open,
  });

  const run = useMutation({
    mutationFn: () => api.post<Job>(`/api/lanes/${laneId}/research`, { top_n: topN }),
    onSuccess: (job) => {
      setJobId(job.id);
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed to start"),
  });

  if (!open) {
    return (
      <button className="btn-ghost" onClick={() => setOpen(true)}>
        Research top-N
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
        {estimate && (
          <span className="text-xs text-slate-500">
            {estimate.lead_count} leads · est. <b>${estimate.estimated_usd.toFixed(2)}</b>
          </span>
        )}
        <button className="btn-primary" disabled={run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? "Starting…" : "Run research"}
        </button>
        <button className="btn-ghost" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Visits each prospect's pages and synthesises a brief — spends real API tokens.
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
