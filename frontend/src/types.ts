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

export interface IntegrationStatus {
  env: string;
  ai: { anthropic: boolean; models: Record<string, string> };
  sources: Record<string, boolean>;
  geo_engines: string[];
  email_resolver: boolean;
  gmail: boolean;
  booking: boolean;
}
