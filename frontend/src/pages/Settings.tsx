import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { JobProgress } from "../components/JobProgress";
import { ApiError, api } from "../lib/api";
import type { GmailStatusInfo, Job, SendingSettings, Suppression } from "../types";

function GmailSection() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["gmail-status"],
    queryFn: () => api.get<GmailStatusInfo>("/api/integrations/gmail/status"),
  });
  const connect = useMutation({
    mutationFn: () => api.get<{ auth_url: string }>("/api/integrations/gmail/connect"),
    onSuccess: (r) => {
      window.location.href = r.auth_url;
    },
    onError: (e) => alert(e instanceof ApiError ? e.message : "Connect failed"),
  });
  const disconnect = useMutation({
    mutationFn: () => api.post("/api/integrations/gmail/disconnect", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["gmail-status"] }),
  });

  return (
    <div className="card p-4">
      <h2 className="mb-2 font-semibold">Gmail (sending account)</h2>
      {!data?.configured ? (
        <p className="text-sm text-amber-700">
          Gmail OAuth not configured — set GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET in .env. Until
          then, the send queue creates simulated drafts so you can test the flow.
        </p>
      ) : data.connected ? (
        <div className="flex items-center justify-between text-sm">
          <span>
            Connected as <b>{data.account_email}</b>
          </span>
          <button className="btn-ghost" onClick={() => disconnect.mutate()}>
            Disconnect
          </button>
        </div>
      ) : (
        <button className="btn-primary" disabled={connect.isPending} onClick={() => connect.mutate()}>
          Connect Gmail
        </button>
      )}
    </div>
  );
}

function SendingSection() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["sending-settings"],
    queryFn: () => api.get<SendingSettings>("/api/settings/sending"),
  });
  const [form, setForm] = useState<Partial<SendingSettings>>({});
  const merged = { ...data, ...form } as SendingSettings;
  const save = useMutation({
    mutationFn: () => api.put<SendingSettings>("/api/settings/sending", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sending-settings"] });
      setForm({});
    },
  });
  const [jobId, setJobId] = useState<number | null>(null);
  const process = useMutation({
    mutationFn: () => api.post<Job>("/api/send/process", { ignore_window: true }),
    onSuccess: (j) => setJobId(j.id),
    onError: (e) => alert(e instanceof ApiError ? e.message : "Failed"),
  });

  if (!data) return null;
  const num = (k: keyof SendingSettings) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: Number(e.target.value) });

  return (
    <div className="card p-4">
      <h2 className="mb-2 font-semibold">Sending</h2>
      <p className="mb-3 text-xs text-slate-500">
        Mode: <b>{merged.mode}</b> (Gmail-draft — creates drafts for you to review &amp; send).
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="label">Sending identity</span>
          <input
            className="input"
            value={merged.identity}
            onChange={(e) => setForm({ ...form, identity: e.target.value })}
          />
        </label>
        <label className="text-sm">
          <span className="label">Daily cap</span>
          <input type="number" className="input" value={merged.daily_cap} onChange={num("daily_cap")} />
        </label>
        <label className="text-sm">
          <span className="label">Window start (UTC hour)</span>
          <input
            type="number"
            className="input"
            value={merged.window_start_hour}
            onChange={num("window_start_hour")}
          />
        </label>
        <label className="text-sm">
          <span className="label">Window end (UTC hour)</span>
          <input
            type="number"
            className="input"
            value={merged.window_end_hour}
            onChange={num("window_end_hour")}
          />
        </label>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <button
          className="btn-ghost"
          disabled={Object.keys(form).length === 0 || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save settings"}
        </button>
        <button className="btn-primary" disabled={process.isPending} onClick={() => process.mutate()}>
          {process.isPending ? "Starting…" : "Process send queue now"}
        </button>
      </div>
      {jobId && (
        <JobProgress jobId={jobId} onDone={() => qc.invalidateQueries({ queryKey: ["leads"] })} />
      )}
    </div>
  );
}

function SuppressionSection() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["suppression"],
    queryFn: () => api.get<Suppression[]>("/api/suppression"),
  });
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const add = useMutation({
    mutationFn: () =>
      api.post("/api/suppression", { email_or_domain: value, reason: reason || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suppression"] });
      setValue("");
      setReason("");
    },
    onError: (e) => alert(e instanceof ApiError ? e.message : "Failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/suppression/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suppression"] }),
  });

  return (
    <div className="card p-4">
      <h2 className="mb-1 font-semibold">Suppression list</h2>
      <p className="mb-3 text-xs text-slate-500">
        Emails or domains here are never contacted — checked at send time. Honour opt-outs here.
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        <input
          className="input w-64"
          placeholder="email or domain"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <input
          className="input w-48"
          placeholder="reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <button className="btn-ghost" disabled={!value.trim() || add.isPending} onClick={() => add.mutate()}>
          Add
        </button>
      </div>
      <div className="divide-y divide-line text-sm">
        {data?.map((s) => (
          <div key={s.id} className="flex items-center justify-between py-1.5">
            <span>
              <span className="font-mono">{s.email_or_domain}</span>
              {s.reason && <span className="ml-2 text-xs text-slate-400">{s.reason}</span>}
            </span>
            <button className="btn-ghost" onClick={() => remove.mutate(s.id)}>
              Remove
            </button>
          </div>
        ))}
        {(data?.length ?? 0) === 0 && <p className="py-2 text-slate-400">Nothing suppressed.</p>}
      </div>
    </div>
  );
}

export function Settings() {
  const banner = new URLSearchParams(window.location.search).get("gmail");
  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-lg font-bold">Settings</h1>
      {banner === "connected" && (
        <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">Gmail connected.</p>
      )}
      {banner === "error" && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">Gmail connection failed.</p>
      )}
      <GmailSection />
      <SendingSection />
      <SuppressionSection />
    </div>
  );
}
