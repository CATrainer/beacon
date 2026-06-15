// Shared API types. Kept in sync with the backend Pydantic schemas.

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface SourceConfig {
  key: string;
  enabled: boolean;
  params: Record<string, unknown>;
}

export interface QualificationRules {
  require_website: boolean;
  min_incorporation_years: number | null;
  chain_blocklist: string[];
  max_locations: number | null;
}

export interface ScoringWeights {
  signals: Record<string, number>;
}

export interface FinalWeights {
  fit: number;
  gap: number;
  reachability: number;
}

export interface GeoConfig {
  query_templates: string[];
}

export interface LaneConfig {
  sources: SourceConfig[];
  qualification: QualificationRules;
  scoring: ScoringWeights;
  final_weights: FinalWeights;
  geo: GeoConfig;
  town_list: string[];
}

export interface Lane {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  config: LaneConfig;
  lead_count: number;
}

export type LeadStage =
  | "sourced"
  | "qualified"
  | "scored"
  | "enriched"
  | "ready"
  | "rejected";

export type LeadStatus =
  | "sourced"
  | "qualified"
  | "researched"
  | "prepped"
  | "queued"
  | "sent"
  | "replied"
  | "call_booked"
  | "audit_sold"
  | "delivered"
  | "retainer"
  | "lost"
  | "rejected"
  | "suppressed";

export interface LeadListItem {
  id: number;
  lane_id: number;
  company: string;
  website: string | null;
  domain: string | null;
  location: string | null;
  stage: LeadStage;
  status: LeadStatus;
  fit_score: number | null;
  gap_score: number | null;
  reachability_score: number | null;
  final_score: number | null;
  score_breakdown: Record<string, unknown>;
  reject_reason: string | null;
  updated_at: string;
}

export interface LeadListResponse {
  items: LeadListItem[];
  total: number;
  limit: number;
  offset: number;
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface Job {
  id: number;
  type: string;
  status: JobStatus;
  lane_id: number | null;
  progress: number;
  total: number;
  message: string | null;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Adapter {
  key: string;
  description: string;
  live: boolean;
}

export interface SourceHit {
  id: number;
  source_key: string;
  source_ref: string | null;
  raw_meta: Record<string, unknown>;
  fetched_at: string;
}

export type EmailConfidence = "high" | "medium" | "low";

export interface ResearchBrief {
  id: number;
  summary: string | null;
  specialisms: string | null;
  high_ticket_services: string[];
  decision_maker_name: string | null;
  decision_maker_role: string | null;
  human_hook: string | null;
  marketing_sophistication: string | null;
  emails_found: string[];
  linkedin_url: string | null;
  pages_fetched: string[];
  model_used: string | null;
  cost_usd: number | null;
  created_at: string;
}

export interface Contact {
  id: number;
  email: string | null;
  email_confidence: EmailConfidence | null;
  source: string | null;
  decision_maker_name: string | null;
  linkedin_url: string | null;
  is_primary: boolean;
}

export type GeoHookType = "absence" | "misrepresentation" | "weak_presence" | "no_gap";

export interface GeoCheck {
  id: number;
  engine: string;
  query: string;
  prospect_named: boolean;
  prospect_recommended: boolean;
  competitors: string[];
  cited_sources: string[];
  hook_type: GeoHookType | null;
  severity: number | null;
  checked_at: string;
}

export type EmailStatus = "draft" | "queued" | "sent" | "replied" | "cancelled";

export interface EmailItem {
  id: number;
  touch_no: number;
  subject: string | null;
  body: string | null;
  status: EmailStatus;
  scheduled_for: string | null;
  sent_at: string | null;
  gmail_thread_id: string | null;
  gmail_draft_id: string | null;
}

export interface Evidence {
  id: number;
  query: string;
  engine: string | null;
  screenshot_path: string;
  uploaded_at: string;
}

export interface AuditQueries {
  queries: string[];
  engines: string[];
}

export interface LeadDetail extends LeadListItem {
  reject_overridden: boolean;
  notes: string | null;
  created_at: string;
  source_hits: SourceHit[];
  research_brief: ResearchBrief | null;
  contact: Contact | null;
  geo_checks: GeoCheck[];
  evidence: Evidence[];
  emails: EmailItem[];
}

export interface CostEstimate {
  lead_count: number;
  per_lead_usd: number;
  estimated_usd: number;
}

export interface ManualEntry {
  company_name: string;
  website?: string | null;
  location?: string | null;
}

export interface SendingSettings {
  mode: string;
  identity: string;
  daily_cap: number;
  window_start_hour: number;
  window_end_hour: number;
  min_spacing_seconds: number;
  max_spacing_seconds: number;
}

export interface SourcingSettings {
  enabled: boolean;
  hour: number;
  limit: number;
}

export interface Suppression {
  id: number;
  email_or_domain: string;
  reason: string | null;
  created_at: string;
}

export interface GmailStatusInfo {
  connected: boolean;
  configured: boolean;
  account_email: string | null;
}

export interface Activity {
  id: number;
  type: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Pipeline {
  counts: Record<string, number>;
}

export interface IntegrationStatus {
  env: string;
  ai: { anthropic: boolean; models: Record<string, string> };
  sources: Record<string, boolean>;
  geo_engines: string[];
  email_resolver: boolean;
  gmail: boolean;
  booking: boolean;
}
