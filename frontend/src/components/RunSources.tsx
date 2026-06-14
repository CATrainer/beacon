import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import type { Job } from "../types";
import { JobProgress } from "./JobProgress";

/** Run a lane's configured sources, with a fixtures toggle for keyless demos. */
export function RunSources({ laneId }: { laneId: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [limit, setLimit] = useState(50);
  const [fixtures, setFixtures] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: () =>
      api.post<Job>(`/api/lanes/${laneId}/source`, {
        limit_per_source: limit,
        force_fixtures: fixtures,
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
        Run sources
      </button>
    );
  }

  return (
    <div className="mt-2 w-full rounded-md border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          <span className="label">Per source</span>
          <input
            type="number"
            min={1}
            max={1000}
            className="input w-24"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={fixtures}
            onChange={(e) => setFixtures(e.target.checked)}
          />
          Use fixtures
        </label>
        <button
          className="btn-primary"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          {run.isPending ? "Starting…" : "Run"}
        </button>
        <button className="btn-ghost" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
      {jobId && (
        <JobProgress
          jobId={jobId}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ["leads"] });
            qc.invalidateQueries({ queryKey: ["lanes"] });
          }}
        />
      )}
    </div>
  );
}
