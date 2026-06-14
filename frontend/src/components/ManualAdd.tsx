import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import type { Job, ManualEntry } from "../types";
import { JobProgress } from "./JobProgress";

/** Paste company names/URLs directly into a lane (manual_paste adapter). */
export function ManualAdd({ laneId }: { laneId: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function parse(): ManualEntry[] {
    // One per line: "Company Name, https://website, Town"
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((line) => {
        const [name, website, location] = line.split(",").map((p) => p.trim());
        return { company_name: name, website: website || null, location: location || null };
      })
      .filter((e) => e.company_name);
  }

  const run = useMutation({
    mutationFn: () =>
      api.post<Job>(`/api/lanes/${laneId}/source`, {
        source_keys: ["manual_paste"],
        manual_entries: parse(),
      }),
    onSuccess: (job) => {
      setJobId(job.id);
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed to add"),
  });

  if (!open) {
    return (
      <button className="btn-ghost" onClick={() => setOpen(true)}>
        Add manually
      </button>
    );
  }

  return (
    <div className="mt-2 w-full rounded-md border border-line bg-canvas p-3">
      <p className="label">One per line: Company, https://website, Town</p>
      <textarea
        className="input font-mono text-xs"
        rows={5}
        placeholder={"Acme Dental, https://acmedental.co.uk, Leeds\nBright Smiles, https://brightsmiles.co.uk"}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="mt-2 flex gap-2">
        <button
          className="btn-primary"
          disabled={run.isPending || !text.trim()}
          onClick={() => run.mutate()}
        >
          {run.isPending ? "Adding…" : "Add"}
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
