import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import type { Job } from "../types";
import { JobProgress } from "./JobProgress";

/** Re-score every non-rejected lead in a lane (after tuning scoring weights). */
export function ReScore({ laneId }: { laneId: number }) {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: () => api.post<Job>(`/api/lanes/${laneId}/rescore`, {}),
    onSuccess: (job) => {
      setJobId(job.id);
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed to start"),
  });

  return (
    <div className="w-full">
      <button className="btn-ghost" disabled={run.isPending} onClick={() => run.mutate()}>
        {run.isPending ? "Starting…" : "Re-score"}
      </button>
      {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
      {jobId && (
        <JobProgress
          jobId={jobId}
          onDone={() => qc.invalidateQueries({ queryKey: ["leads"] })}
        />
      )}
    </div>
  );
}
