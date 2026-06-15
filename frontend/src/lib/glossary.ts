// Central definitions so the same plain-English wording is used everywhere.

export const TIP: Record<string, string> = {
  // --- Scores ---
  fit: "Fit & wealth (0–100): how likely this company is to pay and be worth it, from cheap signals like reviews, rating, high-ticket services and marketing spend. Higher is better.",
  gap: "GEO gap (0–100): how absent they are from AI answers for their key buyer queries. Higher = bigger opportunity — they're not recommended and competitors are.",
  reachability:
    "Reachability (0–100): how easily we can reach the decision-maker — based on email confidence and whether we have a named contact.",
  final:
    "Final score: the overall ranking — a weighted blend of Fit, Gap and Reachability (weights are set per lane). The queue sorts by this.",

  // --- Pipeline stage / status ---
  stage:
    "Funnel stage: where the lead is in processing — Sourced → Qualified → Scored → Enriched (researched + GEO) → Ready.",
  status:
    "CRM status: the outreach lifecycle — Queued → Sent → Replied → Call booked → Audit sold → Delivered → Retainer (or Lost).",

  // --- Contact ---
  emailConfidence:
    "How sure we are the email is deliverable. HIGH = found on their site or verified; MEDIUM = inferred from a pattern; LOW = a guess (don't send). 'LinkedIn-first' = no safe email, reach out on LinkedIn.",

  // --- GEO ---
  geo: "GEO gap pre-check: we run the lane's buyer-intent queries through AI engines (Perplexity etc.) to see whether the prospect is named/recommended and who the competitors are. Triage only — the real evidence is your screenshots.",
  named: "Whether the prospect's business appeared at all in the AI engine's answer.",
  recommended: "Whether the AI engine positively recommended the prospect (not just mentioned).",
  hook: "The angle to lead with: 'absence' (not mentioned), 'weak_presence' (mentioned, not recommended), or 'no_gap' (already recommended — little to sell).",
  severity: "How big the GEO gap is (0–100). Higher means more absent, so more to sell.",

  // --- Sending ---
  sendingMode:
    "Gmail-draft mode: Beacon creates a Gmail draft for each approved lead, ready for you to review and send by hand. (Managed auto-send comes later.)",
  identity: "The email address outreach is sent from (and signed as).",
  dailyCap: "Most emails/drafts to process per day for this sending address — protects your domain reputation. Start low while warming up.",
  sendWindow:
    "Drafts/sends are only processed between these UTC hours, so nothing goes out at odd times.",
  spacing: "Random gap between real sends so you never fire a burst (looks human, protects the domain).",

  // --- Scheduled sourcing ---
  scheduledSourcing:
    "When on, the worker tops up every active lane once a day, pulling NEW companies each run (it resumes where it left off) so the queue keeps growing automatically.",
  perRunLimit: "How many candidates to pull from each source per run.",

  // --- Suppression ---
  suppression:
    "Emails or domains that must never be contacted (opt-outs, existing clients). Checked automatically at send time.",
};

const SIGNAL_TIP: Record<string, string> = {
  high_ticket_services:
    "Do they push high-value treatments/services (implants, Invisalign, aesthetics…)? Found by scanning their site.",
  review_count: "Number of Google reviews — a proxy for size and footfall.",
  rating: "Google star rating (rewards 4.0+).",
  multiple_locations: "Signs they run more than one location/clinic.",
  booking_funnel: "An online booking / 'book now' funnel — a marketing-maturity signal.",
  blog: "An active blog / news section — they invest in content.",
  tracked_ads: "Ad/analytics tracking on the site (Google/Meta) — they spend on marketing.",
  premium_positioning: "Premium / tailor-made / luxury positioning (vs budget/package).",
  bespoke_language: "Bespoke / tailored / made-to-measure language.",
  membership_aito: "Member of AITO (specialist travel association) — strong fit signal.",
  membership_atol_abta: "Holds ATOL / ABTA membership.",
  review_signals: "Combined review volume + rating quality.",
};

export function signalTip(name: string): string {
  return SIGNAL_TIP[name] ?? `Lane-weighted scoring signal: ${name.replace(/_/g, " ")}.`;
}
