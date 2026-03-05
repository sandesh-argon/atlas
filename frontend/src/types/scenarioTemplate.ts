export interface TemplateIntervention {
  indicator_id: string;
  indicator_name: string;
  change_percent: number;
  change_absolute?: number | null;
  justification: string;
  confidence: 'high' | 'medium' | 'low';
}

export interface TemplateOutcomes {
  primary: string;
  secondary: string[];
  time_horizon_years: number;
}

export interface TemplateEvidence {
  source: string;
  case_study: string;
  citations: string[];
}

export type TemplateCategory =
  | 'health' | 'education' | 'infrastructure'
  | 'governance' | 'economy' | 'environment';

export interface ScenarioTemplate {
  id: string;
  name: string;
  short_name: string;
  description: string;
  category: TemplateCategory;
  source: string;
  year: number;
  target_audience: string;
  interventions: TemplateIntervention[];
  expected_outcomes: TemplateOutcomes;
  evidence: TemplateEvidence;
  tags: string[];
  difficulty: 'easy' | 'moderate' | 'hard';
  cost_estimate_usd: string;
  political_feasibility: 'low' | 'medium' | 'high';
}
