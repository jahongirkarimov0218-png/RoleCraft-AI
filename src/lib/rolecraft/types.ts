export interface RoleCraftInput {
  roleTitle: string;
  companyContext: string;
  coreBusinessPain: string;
  techStackAndSkills: string;
}

export interface ThinkingPartnerAnalysis {
  rootProblemAnalysis: string;
  candidateFearsAndDrivers: string;
  strategicAngle: string;
}

export interface RawMetrics {
  clichesRemovedCount: number;
  impactDeliverablesCount: number;
  antiPersonaCriteriaCount: number;
  readabilityScore: number;
  generationDurationMs?: number;
}

export interface RoleCraftOutput {
  thinkingPartner: ThinkingPartnerAnalysis;
  jobDescriptionMarkdown: string;
  rawMetrics: RawMetrics;
}

export interface RoleCraftPreset {
  id: string;
  name: string;
  badge: string;
  input: RoleCraftInput;
}
