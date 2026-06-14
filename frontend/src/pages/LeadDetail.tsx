import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import type { LeadDetail as LeadDetailType } from "../types";

export function LeadDetail() {
  const { id } = useParams();
  const qc = useQueryClient();

  const { data: lead, isLoading } = useQuery({
    queryKey: ["lead", id],
    queryFn: () => api.get<LeadDetailType>(`/api/leads/${id}`),
  });

  const override = useMutation({
    mutationFn: () => api.post<LeadDetailType>(`/api/leads/${id}/override`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead", id] });
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
    onError: (e) => alert(e instanceof ApiError ? e.message : "Override failed"),
  });

  if (isLoading) return <p className="text-sm text-slate-400">Loading…</p>;
  if (!lead) return <p className="text-sm text-red-700">Lead not found.</p>;

  return (
    <div className="max-w-3xl">
      <Link to="/queue" className="text-sm text-accent hover:underline">
        ← Back to queue
      </Link>

      <div className="mt-2 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-bold">{lead.company}</h1>
          {lead.website && (
            <a
              href={lead.website}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-accent hover:underline"
            >
              {lead.domain ?? lead.website}
            </a>
          )}
          <p className="text-sm text-slate-500">{lead.location ?? "—"}</p>
        </div>
        <div className="flex gap-2">
          <span className="badge bg-canvas text-slate-600">{lead.stage}</span>
          <span className="badge bg-canvas text-slate-600">{lead.status}</span>
        </div>
      </div>

      {lead.stage === "rejected" && (
        <div className="card mt-3 border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-800">
            <span className="font-semibold">Rejected at Stage 2:</span> {lead.reject_reason}
          </p>
          <button
            className="btn-ghost mt-2"
            disabled={override.isPending}
            onClick={() => override.mutate()}
          >
            {override.isPending ? "Overriding…" : "Override → qualify anyway"}
          </button>
        </div>
      )}

      <h2 className="mt-5 mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Source hits ({lead.source_hits.length})
      </h2>
      <div className="card divide-y divide-line">
        {lead.source_hits.map((h) => (
          <div key={h.id} className="p-3">
            <div className="flex items-center justify-between">
              <span className="badge bg-blue-50 text-blue-700">{h.source_key}</span>
              {h.source_ref && (
                <span className="font-mono text-xs text-slate-400">{h.source_ref}</span>
              )}
            </div>
            {Object.keys(h.raw_meta).length > 0 && (
              <pre className="mt-2 overflow-x-auto rounded bg-canvas p-2 text-xs text-slate-600">
                {JSON.stringify(h.raw_meta, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {lead.source_hits.length === 0 && (
          <p className="p-3 text-sm text-slate-400">No source hits.</p>
        )}
      </div>
    </div>
  );
}
