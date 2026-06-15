import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { IntegrationStatus, Lane, Pipeline } from "../types";

const STEPS = [
  {
    n: 1,
    title: "Tune a lane",
    body: "A lane defines who you're targeting — its sources, scoring and audit queries.",
    to: "/lanes",
    cta: "Open Lanes",
  },
  {
    n: 2,
    title: "Run sources",
    body: "Pull in real, pre-qualified companies (CQC, Google Places, directories…).",
    to: "/lanes",
    cta: "Run a source",
  },
  {
    n: 3,
    title: "Research & GEO-check the top leads",
    body: "Build a research brief + resolve the contact, then run the GEO gap pre-check.",
    to: "/queue",
    cta: "View the queue",
  },
  {
    n: 4,
    title: "Prep & draft",
    body: "Open a lead, run the audit queries, upload screenshots, and generate the email.",
    to: "/queue",
    cta: "Prep a lead",
  },
  {
    n: 5,
    title: "Copy into Gmail & send",
    body: "Copy the recipient, subject and body straight into Gmail. Track replies here.",
    to: "/pipeline",
    cta: "See the pipeline",
  },
];

function StatusChip({ label, on, note }: { label: string; on: boolean; note: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-line bg-white p-2.5">
      <span
        className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${on ? "bg-green-500" : "bg-slate-300"}`}
      />
      <div>
        <div className="text-sm font-medium">
          {label} <span className="text-xs text-slate-400">{on ? "live" : "add key"}</span>
        </div>
        <div className="text-xs text-slate-500">{note}</div>
      </div>
    </div>
  );
}

export function Home() {
  const { user } = useAuth();
  const { data: status } = useQuery({
    queryKey: ["status"],
    queryFn: () => api.get<IntegrationStatus>("/api/status"),
  });
  const { data: pipeline } = useQuery({
    queryKey: ["pipeline"],
    queryFn: () => api.get<Pipeline>("/api/pipeline"),
  });
  const { data: lanes } = useQuery({
    queryKey: ["lanes"],
    queryFn: () => api.get<Lane[]>("/api/lanes"),
  });

  const counts = pipeline?.counts ?? {};
  const totalLeads = Object.values(counts).reduce((a, b) => a + b, 0);

  const snapshot = [
    { key: "scored", label: "Scored" },
    { key: "researched", label: "Researched" },
    { key: "queued", label: "Queued" },
    { key: "sent", label: "Sent" },
    { key: "call_booked", label: "Calls booked" },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-bold">Welcome back{user ? `, ${user.name.split(" ")[0]}` : ""}</h1>
        <p className="text-sm text-slate-500">
          Beacon finds, ranks and researches potential clients, then helps you draft the outreach.
          Here's how to get to a sent email.
        </p>
      </div>

      {/* Getting started */}
      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Get started
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="card flex flex-col p-4">
              <div className="mb-1 flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">
                  {s.n}
                </span>
                <h3 className="font-semibold">{s.title}</h3>
              </div>
              <p className="flex-1 text-sm text-slate-500">{s.body}</p>
              <Link to={s.to} className="btn-ghost mt-3 self-start">
                {s.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline snapshot */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Pipeline snapshot
          </h2>
          <Link to="/pipeline" className="text-sm text-accent hover:underline">
            Full pipeline →
          </Link>
        </div>
        {totalLeads === 0 ? (
          <div className="card p-4 text-sm text-slate-500">
            No leads yet. Head to{" "}
            <Link to="/lanes" className="text-accent hover:underline">
              Lanes
            </Link>{" "}
            and run a source to fill the queue.
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {snapshot.map((s) => (
              <Link key={s.key} to={`/queue?status=${s.key}`} className="card p-3 hover:bg-canvas">
                <div className="text-2xl font-bold">{counts[s.key] ?? 0}</div>
                <div className="text-xs text-slate-500">{s.label}</div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Integrations */}
      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Integrations
        </h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <StatusChip
            label="Anthropic"
            on={!!status?.ai.anthropic}
            note="Research briefs, drafting, GEO extraction"
          />
          <StatusChip label="CQC" on={!!status?.sources.cqc} note="Clinics source (England)" />
          <StatusChip
            label="Google Places"
            on={!!status?.sources.google_places}
            note="Wealth signals: reviews & rating"
          />
          <StatusChip
            label="GEO engines"
            on={(status?.geo_engines.length ?? 0) > 0}
            note={
              (status?.geo_engines.length ?? 0) > 0
                ? status!.geo_engines.join(", ")
                : "Add Perplexity for real GEO triage"
            }
          />
          <StatusChip
            label="Gmail"
            on={!!status?.gmail}
            note="Optional — drafts are simulated until connected"
          />
          <StatusChip
            label="Companies House"
            on={!!status?.sources.companies_house}
            note="Optional — director names"
          />
        </div>
      </div>

      {/* Lanes quick access */}
      {lanes && lanes.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Your lanes
          </h2>
          <div className="flex flex-wrap gap-2">
            {lanes.map((l) => (
              <Link key={l.id} to="/lanes" className="card px-3 py-2 text-sm hover:bg-canvas">
                <span className="font-medium">{l.name}</span>{" "}
                <span className="text-slate-400">· {l.lead_count} leads</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
