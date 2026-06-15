import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { JobProgress } from "../components/JobProgress";
import { PrepChecklist } from "../components/PrepChecklist";
import { ApiError, api } from "../lib/api";
import type { Activity, EmailConfidence, Job, LeadDetail as LeadDetailType } from "../types";

const STATUS_OPTIONS = [
  "sourced", "qualified", "researched", "prepped", "queued", "sent", "replied",
  "call_booked", "audit_sold", "delivered", "retainer", "lost", "rejected", "suppressed",
];

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

const QUEUED_STATUSES = [
  "queued", "sent", "replied", "call_booked", "audit_sold", "delivered", "retainer",
];

function StepBar({ lead }: { lead: LeadDetailType }) {
  const researched = !!lead.research_brief;
  const geoChecked = lead.geo_checks.some((g) => g.engine !== "none");
  const drafted = lead.emails.length > 0;
  const queued = QUEUED_STATUSES.includes(lead.status);
  const steps = [
    { label: "Sourced", done: true },
    { label: "Qualified", done: true },
    { label: "Scored", done: lead.fit_score != null },
    { label: "Researched", done: researched },
    { label: "GEO", done: geoChecked },
    { label: "Drafted", done: drafted },
    { label: "Queued", done: queued },
  ];
  let next: { text: string; id: string } | null = null;
  if (!researched) next = { text: "Research this lead", id: "research" };
  else if (!geoChecked) next = { text: "Run the GEO check", id: "geo" };
  else if (!drafted) next = { text: "Generate the email drafts", id: "prep" };
  else if (!queued) next = { text: "Review, copy & approve", id: "prep" };

  return (
    <div className="card mt-3 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {steps.map((s, i) => (
          <span key={s.label} className="flex items-center gap-1.5">
            <span
              className={`badge ${
                s.done ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-500"
              }`}
            >
              {s.done ? "✓" : "○"} {s.label}
            </span>
            {i < steps.length - 1 && <span className="text-slate-300">›</span>}
          </span>
        ))}
      </div>
      {next ? (
        <div className="mt-2 flex items-center gap-2 text-sm">
          <span className="text-slate-500">Next step:</span>
          <button className="btn-primary" onClick={() => scrollToId(next!.id)}>
            {next.text} ↓
          </button>
        </div>
      ) : (
        <p className="mt-2 text-sm text-green-700">
          Ready to send — copy the email below into Gmail.
        </p>
      )}
    </div>
  );
}

function confidenceBadge(c: EmailConfidence | null) {
  if (!c) return <span className="badge bg-slate-100 text-slate-500">LinkedIn-first</span>;
  const tone =
    c === "high"
      ? "bg-green-100 text-green-800"
      : c === "medium"
        ? "bg-amber-100 text-amber-800"
        : "bg-red-100 text-red-700";
  return <span className={`badge ${tone}`}>{c} confidence</span>;
}

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

  const [researchJobId, setResearchJobId] = useState<number | null>(null);
  const research = useMutation({
    mutationFn: () =>
      api.post<Job>(`/api/lanes/${lead?.lane_id}/research`, { lead_ids: [Number(id)] }),
    onSuccess: (job) => setResearchJobId(job.id),
    onError: (e) => alert(e instanceof ApiError ? e.message : "Research failed"),
  });

  const [geoFixtures, setGeoFixtures] = useState(false);
  const [geoJobId, setGeoJobId] = useState<number | null>(null);
  const geo = useMutation({
    mutationFn: () =>
      api.post<Job>(`/api/lanes/${lead?.lane_id}/geo`, {
        lead_ids: [Number(id)],
        force_fixtures: geoFixtures,
      }),
    onSuccess: (job) => setGeoJobId(job.id),
    onError: (e) => alert(e instanceof ApiError ? e.message : "GEO check failed"),
  });

  const { data: activity } = useQuery({
    queryKey: ["activity", id],
    queryFn: () => api.get<Activity[]>(`/api/leads/${id}/activity`),
  });
  const setStatus = useMutation({
    mutationFn: (s: string) => api.patch(`/api/leads/${id}/status`, { status: s }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead", id] });
      qc.invalidateQueries({ queryKey: ["activity", id] });
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
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
        <div className="flex items-center gap-2">
          <span className="badge bg-canvas text-slate-600">{lead.stage}</span>
          <select
            className="input w-40 text-xs"
            value={lead.status}
            onChange={(e) => setStatus.mutate(e.target.value)}
            title="Move pipeline stage"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
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

      {lead.stage !== "rejected" && <StepBar lead={lead} />}

      <ScoreBreakdown lead={lead} />

      {/* Contact */}
      <div className="card mt-4 p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Contact
          </h2>
          {lead.contact && confidenceBadge(lead.contact.email_confidence)}
        </div>
        {lead.contact ? (
          <div className="space-y-1 text-sm">
            <div>
              {lead.contact.email ? (
                <span className="font-mono">{lead.contact.email}</span>
              ) : (
                <span className="text-slate-500">No deliverable email — reach out on LinkedIn</span>
              )}
              {lead.contact.source && (
                <span className="ml-2 text-xs text-slate-400">via {lead.contact.source}</span>
              )}
            </div>
            {lead.contact.decision_maker_name && (
              <div className="text-slate-600">{lead.contact.decision_maker_name}</div>
            )}
            {lead.contact.linkedin_url && (
              <a
                href={lead.contact.linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                LinkedIn
              </a>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Not yet resolved — run research.</p>
        )}
      </div>

      {/* Research brief */}
      <div id="research" className="card mt-4 scroll-mt-4 p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Research brief
          </h2>
          <button
            className="btn-ghost"
            disabled={research.isPending}
            onClick={() => research.mutate()}
          >
            {research.isPending ? "Starting…" : lead.research_brief ? "Re-research" : "Research this lead"}
          </button>
        </div>
        {researchJobId && (
          <JobProgress
            jobId={researchJobId}
            onDone={() => {
              qc.invalidateQueries({ queryKey: ["lead", id] });
              qc.invalidateQueries({ queryKey: ["leads"] });
            }}
          />
        )}
        {lead.research_brief ? (
          <div className="mt-1 space-y-2 text-sm">
            {lead.research_brief.summary && <p>{lead.research_brief.summary}</p>}
            {lead.research_brief.decision_maker_name && (
              <p>
                <span className="text-slate-500">Decision-maker: </span>
                {lead.research_brief.decision_maker_name}
                {lead.research_brief.decision_maker_role
                  ? ` — ${lead.research_brief.decision_maker_role}`
                  : ""}
              </p>
            )}
            {lead.research_brief.high_ticket_services.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {lead.research_brief.high_ticket_services.map((s) => (
                  <span key={s} className="badge bg-blue-50 text-blue-700">
                    {s}
                  </span>
                ))}
              </div>
            )}
            {lead.research_brief.human_hook && (
              <p>
                <span className="text-slate-500">Hook: </span>
                {lead.research_brief.human_hook}
              </p>
            )}
            {lead.research_brief.marketing_sophistication && (
              <p>
                <span className="text-slate-500">Marketing: </span>
                {lead.research_brief.marketing_sophistication}
              </p>
            )}
            {lead.research_brief.emails_found.length > 0 && (
              <p className="text-xs text-slate-500">
                Emails found: {lead.research_brief.emails_found.join(", ")}
              </p>
            )}
            <p className="text-xs text-slate-400">
              {lead.research_brief.pages_fetched.length} pages ·{" "}
              {lead.research_brief.model_used ?? "no LLM"} ·{" "}
              {lead.research_brief.cost_usd != null
                ? `$${lead.research_brief.cost_usd.toFixed(3)}`
                : "—"}
            </p>
          </div>
        ) : (
          <p className="mt-1 text-sm text-slate-500">
            Not yet researched. Stage 4 spends API tokens, so run it on shortlisted leads.
          </p>
        )}
      </div>

      {/* GEO pre-check (triage only) */}
      <div id="geo" className="card mt-4 scroll-mt-4 p-4">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            GEO gap pre-check
          </h2>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1 text-xs text-slate-500">
              <input
                type="checkbox"
                checked={geoFixtures}
                onChange={(e) => setGeoFixtures(e.target.checked)}
              />
              fixtures
            </label>
            <button className="btn-ghost" disabled={geo.isPending} onClick={() => geo.mutate()}>
              {geo.isPending ? "Starting…" : "Run GEO check"}
            </button>
          </div>
        </div>
        <p className="mb-2 text-xs text-slate-400">
          Triage for ranking & hook detection only — not the deliverable audit. The real evidence
          is the screenshots you capture in the consumer apps during prep.
        </p>
        {geoJobId && (
          <JobProgress
            jobId={geoJobId}
            onDone={() => {
              qc.invalidateQueries({ queryKey: ["lead", id] });
              qc.invalidateQueries({ queryKey: ["leads"] });
            }}
          />
        )}
        {lead.geo_checks.length === 0 ? (
          <p className="text-sm text-slate-500">Not yet checked.</p>
        ) : (
          <div className="space-y-2">
            {lead.geo_checks.map((g) => (
              <div key={g.id} className="rounded border border-line p-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="badge bg-slate-100 text-slate-600">{g.engine}</span>
                  {g.hook_type && (
                    <span
                      className={`badge ${
                        g.hook_type === "no_gap"
                          ? "bg-slate-100 text-slate-500"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {g.hook_type} {g.severity != null ? `· sev ${g.severity}` : ""}
                    </span>
                  )}
                </div>
                {g.engine !== "none" && (
                  <>
                    <div className="mt-1 text-slate-600">“{g.query}”</div>
                    <div className="mt-1 text-slate-500">
                      named: {g.prospect_named ? "yes" : "no"} · recommended:{" "}
                      {g.prospect_recommended ? "yes" : "no"}
                    </div>
                    {g.competitors.length > 0 && (
                      <div className="mt-1">
                        competitors:{" "}
                        {g.competitors.map((c) => (
                          <span key={c} className="badge ml-1 bg-amber-50 text-amber-800">
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div id="prep" className="scroll-mt-4">
        <PrepChecklist lead={lead} />
      </div>

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

      <h2 className="mt-5 mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Activity
      </h2>
      <div className="card divide-y divide-line text-sm">
        {(activity ?? []).map((a) => (
          <div key={a.id} className="flex items-center justify-between px-3 py-1.5">
            <span>{a.type.replace(/_/g, " ")}</span>
            <span className="text-xs text-slate-400">
              {new Date(a.created_at).toLocaleString()}
            </span>
          </div>
        ))}
        {(activity?.length ?? 0) === 0 && (
          <p className="p-3 text-slate-400">No activity yet.</p>
        )}
      </div>
    </div>
  );
}
