import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { API_BASE, ApiError, api } from "../lib/api";
import type { AuditQueries, EmailItem, LeadDetail } from "../types";

const ENGINES = ["ChatGPT", "Gemini", "Perplexity"];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn-ghost"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function wordCount(s: string | null): number {
  return (s ?? "").trim().split(/\s+/).filter(Boolean).length;
}

function EmailEditor({ email, onSaved }: { email: EmailItem; onSaved: () => void }) {
  const [subject, setSubject] = useState(email.subject ?? "");
  const [body, setBody] = useState(email.body ?? "");
  const save = useMutation({
    mutationFn: () => api.patch(`/api/emails/${email.id}`, { subject, body }),
    onSuccess: onSaved,
    onError: (e) => alert(e instanceof ApiError ? e.message : "Save failed"),
  });
  const wc = wordCount(body);
  const wcTone = wc >= 60 && wc <= 110 ? "text-green-700" : "text-amber-700";
  const editable = email.status === "draft";
  return (
    <div className="rounded border border-line p-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="badge bg-canvas text-slate-600">
          Touch {email.touch_no} · {email.status}
        </span>
        <span className={`text-xs ${wcTone}`}>{wc} words (target 60–110)</span>
      </div>
      <input
        className="input mb-2"
        value={subject}
        disabled={!editable}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject"
      />
      <textarea
        className="input font-mono text-xs"
        rows={8}
        value={body}
        disabled={!editable}
        onChange={(e) => setBody(e.target.value)}
      />
      {editable && (
        <button className="btn-ghost mt-2" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save edits"}
        </button>
      )}
    </div>
  );
}

export function PrepChecklist({ lead }: { lead: LeadDetail }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["lead", String(lead.id)] });

  const { data: audit } = useQuery({
    queryKey: ["audit-queries", lead.id],
    queryFn: () => api.get<AuditQueries>(`/api/leads/${lead.id}/audit-queries`),
  });

  const draft = useMutation({
    mutationFn: () => api.post<EmailItem[]>(`/api/leads/${lead.id}/draft`, {}),
    onSuccess: refresh,
    onError: (e) => alert(e instanceof ApiError ? e.message : "Draft failed"),
  });

  const approve = useMutation({
    mutationFn: () => api.post(`/api/leads/${lead.id}/approve`, {}),
    onSuccess: () => {
      refresh();
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
    onError: (e) => alert(e instanceof ApiError ? e.message : "Approve failed"),
  });

  const upload = useMutation({
    mutationFn: ({ query, engine, file }: { query: string; engine: string; file: File }) => {
      const form = new FormData();
      form.append("query", query);
      form.append("engine", engine);
      form.append("file", file);
      return api.upload(`/api/leads/${lead.id}/evidence`, form);
    },
    onSuccess: refresh,
    onError: (e) => alert(e instanceof ApiError ? e.message : "Upload failed"),
  });

  const delEvidence = useMutation({
    mutationFn: (id: number) => api.del(`/api/evidence/${id}`),
    onSuccess: refresh,
  });

  const [engineByQuery, setEngineByQuery] = useState<Record<string, string>>({});
  const touch1 = lead.emails.find((e) => e.touch_no === 1);
  const canApprove = !!touch1 && !!(touch1.body ?? "").trim();

  return (
    <div className="card mt-4 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Prep checklist
      </h2>

      {/* 1. Audit queries + screenshot upload */}
      <div className="mb-5">
        <h3 className="mb-1 text-sm font-semibold">1 · Run audit queries & upload screenshots</h3>
        <p className="mb-2 text-xs text-slate-500">
          Paste each query into the real {audit?.engines.join(" / ")} apps, then upload the
          screenshot. This is the irreducible manual step — the real evidence.
        </p>
        <div className="space-y-2">
          {audit?.queries.map((q) => {
            const shots = lead.evidence.filter((e) => e.query === q);
            const engine = engineByQuery[q] ?? "ChatGPT";
            return (
              <div key={q} className="rounded border border-line p-2">
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs">{q}</code>
                  <CopyButton text={q} />
                </div>
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <select
                    className="input w-32"
                    value={engine}
                    onChange={(e) => setEngineByQuery({ ...engineByQuery, [q]: e.target.value })}
                  >
                    {ENGINES.map((en) => (
                      <option key={en}>{en}</option>
                    ))}
                  </select>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) upload.mutate({ query: q, engine, file });
                      e.target.value = "";
                    }}
                  />
                </div>
                {shots.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {shots.map((s) => (
                      <div key={s.id} className="relative">
                        <a href={`${API_BASE}${s.screenshot_path}`} target="_blank" rel="noreferrer">
                          <img
                            src={`${API_BASE}${s.screenshot_path}`}
                            alt={s.engine ?? "evidence"}
                            className="h-16 w-24 rounded border border-line object-cover"
                          />
                        </a>
                        <button
                          className="absolute -right-1 -top-1 rounded-full bg-red-600 px-1 text-xs text-white"
                          onClick={() => delEvidence.mutate(s.id)}
                          title="Delete"
                        >
                          ×
                        </button>
                        <div className="text-center text-[10px] text-slate-400">{s.engine}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Drafted emails */}
      <div className="mb-5">
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-sm font-semibold">2 · Review & edit the drafted emails</h3>
          <button className="btn-ghost" disabled={draft.isPending} onClick={() => draft.mutate()}>
            {draft.isPending ? "Drafting…" : lead.emails.length ? "Re-draft" : "Generate drafts"}
          </button>
        </div>
        {lead.emails.length === 0 ? (
          <p className="text-xs text-slate-500">
            No drafts yet. Generate after research + screenshots for the best touch-1.
          </p>
        ) : (
          <div className="space-y-3">
            {lead.emails.map((e) => (
              <EmailEditor key={e.id} email={e} onSaved={refresh} />
            ))}
          </div>
        )}
      </div>

      {/* 3. Approve */}
      <div>
        <h3 className="mb-1 text-sm font-semibold">3 · Approve → send queue</h3>
        <p className="mb-2 text-xs text-slate-500">
          Confirm the contact and the two call slots in the touch-1 body, then approve to move this
          lead into the send queue.
        </p>
        <button
          className="btn-primary"
          disabled={!canApprove || approve.isPending || lead.status === "queued"}
          onClick={() => approve.mutate()}
        >
          {lead.status === "queued"
            ? "Queued ✓"
            : approve.isPending
              ? "Approving…"
              : "Approve → queue"}
        </button>
        {!canApprove && (
          <span className="ml-2 text-xs text-amber-700">Draft the touch-1 email first.</span>
        )}
      </div>
    </div>
  );
}
