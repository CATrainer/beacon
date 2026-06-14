import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../lib/api";
import type { Job } from "../types";

/** Polls a job until it finishes, rendering a compact progress line. */
export function JobProgress({ jobId, onDone }: { jobId: number; onDone?: () => void }) {
  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<Job>(`/api/jobs/${jobId}`),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "succeeded" || s === "failed" ? false : 1000;
    },
  });

  useEffect(() => {
    if (job && (job.status === "succeeded" || job.status === "failed")) onDone?.();
  }, [job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!job) return null;

  const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
  const tone =
    job.status === "failed"
      ? "text-red-700"
      : job.status === "succeeded"
        ? "text-green-700"
        : "text-slate-600";

  return (
    <div className="mt-2 text-xs">
      <div className={`mb-1 font-medium ${tone}`}>
        {job.status === "running" && `Running — ${job.message ?? "working…"}`}
        {job.status === "queued" && "Queued…"}
        {job.status === "succeeded" && (job.message ?? "Done")}
        {job.status === "failed" && `Failed: ${job.error ?? "unknown error"}`}
      </div>
      {(job.status === "running" || job.status === "queued") && (
        <div className="h-1.5 w-full overflow-hidden rounded bg-canvas">
          <div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}
