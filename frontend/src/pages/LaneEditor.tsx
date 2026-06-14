import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import type { Lane, LaneConfig } from "../types";

const DEFAULT_CONFIG: LaneConfig = {
  sources: [{ key: "manual_paste", enabled: true, params: {} }],
  qualification: {
    require_website: true,
    min_incorporation_years: 2,
    chain_blocklist: [],
    max_locations: null,
  },
  scoring: { signals: {} },
  final_weights: { fit: 0.5, gap: 0.3, reachability: 0.2 },
  geo: { query_templates: [] },
  town_list: [],
};

export function LaneEditor() {
  const { id } = useParams();
  const isNew = !id;
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [configText, setConfigText] = useState(JSON.stringify(DEFAULT_CONFIG, null, 2));
  const [error, setError] = useState<string | null>(null);

  const { data: lane } = useQuery({
    queryKey: ["lane", id],
    queryFn: () => api.get<Lane>(`/api/lanes/${id}`),
    enabled: !isNew,
  });

  useEffect(() => {
    if (lane) {
      setName(lane.name);
      setDescription(lane.description);
      setIsActive(lane.is_active);
      setConfigText(JSON.stringify(lane.config, null, 2));
    }
  }, [lane]);

  const save = useMutation({
    mutationFn: async () => {
      let config: unknown;
      try {
        config = JSON.parse(configText);
      } catch {
        throw new ApiError(422, "Config is not valid JSON.");
      }
      const body = { name, description, is_active: isActive, config };
      if (isNew) return api.post<Lane>("/api/lanes", body);
      return api.patch<Lane>(`/api/lanes/${id}`, body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lanes"] });
      navigate("/lanes");
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Save failed"),
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutate();
  }

  return (
    <form onSubmit={onSubmit} className="max-w-3xl">
      <h1 className="mb-4 text-lg font-bold">{isNew ? "New lane" : `Edit: ${lane?.name ?? ""}`}</h1>

      <div className="card mb-3 space-y-3 p-4">
        <div>
          <label className="label" htmlFor="name">
            Name
          </label>
          <input
            id="name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="desc">
            Description
          </label>
          <textarea
            id="desc"
            className="input"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Active
        </label>
      </div>

      <div className="card mb-3 p-4">
        <label className="label" htmlFor="config">
          Config (sources, qualification, scoring, final weights, GEO templates, town list)
        </label>
        <p className="mb-2 text-xs text-slate-500">
          Edited as JSON for now; structured editors for sources and scoring arrive with those
          slices. The backend validates the shape on save.
        </p>
        <textarea
          id="config"
          className="input font-mono text-xs"
          rows={22}
          spellCheck={false}
          value={configText}
          onChange={(e) => setConfigText(e.target.value)}
        />
      </div>

      {error && (
        <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save lane"}
        </button>
        <button type="button" className="btn-ghost" onClick={() => navigate("/lanes")}>
          Cancel
        </button>
      </div>
    </form>
  );
}
