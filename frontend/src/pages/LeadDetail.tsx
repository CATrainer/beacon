import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import type { LeadDetail as LeadDetailType } from "../types";

interface SignalRow {
  weight: number;
  strength: number;
  contribution: number;
}

function ScoreBreakdown({ lead }: { lead: LeadDetailType }) {
  const bd = lead.score_breakdown as {
    signals?: Record<string, SignalRow>;
    total_weight?: number;
    context?: { review_count?: number; rating?: number | null; homepage_fetched?: boolean };
  };
  const signals = bd?.signals ?? {};
  const names = Object.keys(signals);
  if (lead.fit_score == null && names.length === 0) {
    return (
      <div className="card mt-4 p-4 text-sm text-slate-500">
        Not yet scored — run sources or re-score this lane.
      </div>
    );
  }
  return (
    <div className="card mt-4 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Score breakdown
        </h2>
        <div className="flex gap-3 text-sm">
          <span>
            Fit <b>{lead.fit_score ?? "—"}</b>
          </span>
          <span>
            Gap <b>{lead.gap_score ?? "—"}</b>
          </span>
          <span>
            Reach <b>{lead.reachability_score ?? "—"}</b>
          </span>
          <span className="text-accent">
            Final <b>{lead.final_score ?? "—"}</b>
          </span>
        </div>
      </div>
      <div className="space-y-1.5">
        {names.map((name) => {
          const s = signals[name];
          return (
            <div key={name} className="flex items-center gap-2 text-xs">
              <span className="w-40 shrink-0 text-slate-600">{name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded bg-canvas">
                <div
                  className="h-full bg-accent"
                  style={{ width: `${Math.round(s.strength * 100)}%` }}
                />
              </div>
              <span className="w-28 shrink-0 text-right text-slate-400">
                w{s.weight} · +{s.contribution}
              </span>
            </div>
          );
        })}
      </div>
      {bd?.context && (
        <p className="mt-3 text-xs text-slate-400">
          {bd.context.review_count ?? 0} reviews · rating {bd.context.rating ?? "—"} ·
          homepage {bd.context.homepage_fetched ? "fetched" : "not fetched"}
        </p>
      )}
    </div>
  );
}

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

      <ScoreBreakdown lead={lead} />

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
