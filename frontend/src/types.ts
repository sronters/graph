export type Dataset = {
  dataset_id: string;
  profile: string;
  scale: string;
  variant: string;
  seed: number;
  path: string;
  counts: Record<string, number>;
  warnings: string[];
};

export type AnalysisJob = {
  analysis_id: string;
  dataset_id: string;
  methods: string[];
  status: "queued" | "running" | "succeeded" | "failed";
  error: string | null;
};

export type Identity = {
  method: string;
  node_id: string;
  node_type: string;
  display_name: string;
  provider: string;
  environment: string;
  department: string;
  identity_status: string;
  privilege_label: string;
  critical_reach: number;
  best_path: number;
  path_diversity: number;
  blast_radius: number;
  control_weakness: number;
  ztri: number;
};

export type PathStep = {
  position: number;
  actor_before: string;
  actor_after: string;
  target_id: string;
  capability: string;
  transition_type: string;
  condition_state: string;
  relative_exploitability: number;
  raw_evidence_edge_ids: string[];
};

export type Finding = {
  finding_id: string;
  method: string;
  source_identity_id: string;
  target_asset_id: string;
  path: PathStep[];
  risk: { path_risk: number; transition_cost: number; criticality: number };
  search: { search_complete: boolean; truncation_reason: string | null };
  caveats: string[];
};

export type Experiment = {
  run_id: string;
  dataset_id: string;
  method: string;
  completed_at: string;
  warnings: string[];
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };
