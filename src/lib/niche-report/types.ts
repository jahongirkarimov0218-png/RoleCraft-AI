/**
 * Niche Report — data contract (intent/spec.md D-03).
 * The report is static data validated at test time; nothing is generated at runtime.
 */

export type CandidateId = "clinic-ops" | "smb-marketing";
export type EvidenceKind = "fact" | "assumption" | "unknown";
export type ReportStatus = "draft" | "final";

export interface Source {
  title: string;
  publisher: string;
  /** https: only */
  url: string;
  /** ISO date the source was accessed, e.g. "2026-10-12" */
  accessedAt: string;
}

export interface Evidence {
  claim: string;
  kind: EvidenceKind;
  /** Required when kind === "fact" */
  source?: Source;
}

export interface Criterion {
  id: string;
  label: string;
  /** 0..1, all weights sum to 1 */
  weight: number;
  /** Why this weight, with a reference to a constraint from the intent */
  rationale: string;
}

export interface Score {
  criterionId: string;
  value: 1 | 2 | 3 | 4 | 5;
  evidence: Evidence[];
}

export interface Candidate {
  id: CandidateId;
  label: string;
  scores: Score[];
}

export interface ValidationTest {
  durationDays: 14;
  audience: string;
  /** What the founder does — describes the problem, never the product */
  action: string;
  metric: string;
  threshold: { value: number; unit: string };
  /** "if ≥ threshold — go" */
  goRule: string;
  fallbackCandidateId: CandidateId;
}

export interface VerdictReason {
  text: string;
  criterionIds: string[];
}

export interface NicheReport {
  meta: {
    title: string;
    author: string;
    status: ReportStatus;
    /** ISO date */
    generatedAt: string;
    version: string;
  };
  verdict: { candidateId: CandidateId; reasons: VerdictReason[] };
  criteria: Criterion[];
  candidates: [Candidate, Candidate];
  test: ValidationTest;
  unknowns: string[];
}
