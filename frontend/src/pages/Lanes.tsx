import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { GeoCheckLane } from "../components/GeoCheckLane";
import { ManualAdd } from "../components/ManualAdd";
import { ReScore } from "../components/ReScore";
import { ResearchLane } from "../components/ResearchLane";
import { RunSources } from "../components/RunSources";
import { ApiError, api } from "../lib/api";
import type { Lane } from "../types";

export function Lanes() {
  const qc = useQueryClient();
  const { data: lanes, isLoading } = useQuery({
    queryKey: ["lanes"],
    queryFn: () => api.get<Lane[]>("/api/lanes"),
  });

  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/lanes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lanes"] }),
    onError: (e) => alert(e instanceof ApiError ? e.message : "Delete failed"),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">Lanes</h1>
          <p className="text-sm text-slate-500">
            A lane is a configurable target segment — sources, qualification, scoring and GEO
            queries, all editable here without a code change.
          </p>
        </div>
        <Link to="/lanes/new" className="btn-primary">
          New lane
        </Link>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {lanes?.map((lane) => (
          <div key={lane.id} className="card p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">{lane.name}</h2>
                  {!lane.is_active && (
                    <span className="badge bg-slate-100 text-slate-500">inactive</span>
                  )}
                </div>
                <p className="mt-0.5 text-sm text-slate-500">{lane.description || "—"}</p>
              </div>
              <span className="badge bg-canvas text-slate-600">{lane.lead_count} leads</span>
            </div>

            <div className="mt-3 flex flex-wrap gap-1">
              {lane.config.sources
                ?.filter((s) => s.enabled)
                .map((s) => (
                  <span key={s.key} className="badge bg-blue-50 text-blue-700">
                    {s.key}
                  </span>
                ))}
            </div>

            <div className="mt-4 border-t border-line pt-3">
              <p className="label">Pipeline — run left to right</p>
              <div className="flex flex-wrap items-start gap-2">
                <RunSources laneId={lane.id} />
                <ManualAdd laneId={lane.id} />
                <ResearchLane laneId={lane.id} />
                <GeoCheckLane laneId={lane.id} />
                <ReScore laneId={lane.id} />
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-start gap-2 border-t border-line pt-3">
              <Link to={`/lanes/${lane.id}`} className="btn-ghost">
                Edit lane
              </Link>
              <button
                className="btn-danger"
                onClick={() => {
                  if (confirm(`Delete lane "${lane.name}"?`)) del.mutate(lane.id);
                }}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
