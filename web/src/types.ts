export type Tab = "flow" | "findings" | "evidence";
export type View = "run" | "records" | "repositories" | "integrations";
export type SourceContext = {
  schema_version: number;
  provenance: "captured" | "historical";
  captured_at: string | null;
  repository: {
    id: string;
    name: string;
    path: string | null;
    kind: string;
    branch: string | null;
    commit: string | null;
    remote: string | null;
    remote_configured?: boolean;
    requested_kind?: "branch" | "commit";
    requested_ref?: string;
    scoped_changes: number | null;
    untracked: number | null;
  };
  target: {
    name: string;
    variant: string;
    kind: string;
    environment: string;
    url: string | null;
  };
  scope: {
    kind: string;
    description: string;
    file_count?: number;
    files: { path: string; sha256: string; size: number }[];
    check_count: number;
  };
  snapshot: { algorithm: string; digest: string };
  tooling: {
    model: string | null;
    executors: string[];
    versions: Record<string, string | null>;
    gate: string | null;
    opa_image: string | null;
  };
};
export type Criterion = {
  id: string;
  kind?: string;
  case_id: string;
  layer: string;
  executor: string;
  title: string;
  expected: string;
  severity: string;
  impact: string;
  required: boolean;
};
export type Artifact = {
  owner_label?: string;
  id: string;
  name: string;
  media_type: string;
  sha256: string;
  size: number;
  criterion_id: string | null;
  collected_at: string;
};
export type Result = {
  criterion_id: string;
  case_id: string;
  layer: string;
  attempt: number;
  status: string;
  duration_ms?: number;
  expected: string;
  actual: string;
  evidence_refs: string[];
  raw_status?: string;
  review?: Review;
};
export type Review = {
  category: string;
  label: string;
  reason: string;
  non_blocking: boolean;
  pending: number;
  non_actionable: number;
  raw_count: number;
  rows: {
    reason: string;
    path?: string;
    line?: number | null;
    rule?: string;
  }[];
};
export type Finding = Result & {
  id: string;
  title: string;
  priority?: "P0" | "P1" | "P2" | "P3";
  severity: string;
  verification: string;
  impact: string;
  review_state?: string;
  review_revision?: string;
  fingerprint?: string;
  occurrences?: string[];
  occurrence_tasks?: string[];
};
export type Inspection = {
  criterion_id: string;
  status: string;
  subject: string;
  steps: string[];
  limitation: string;
  method: string;
  summary: string;
  observation: string;
  verified: boolean;
  expected_value: string;
  actual_value: string | null;
  comparison_labels?: [string, string];
  primary_ref?: string;
  source_report?: string;
  axe_ref?: string;
  location?: string;
  snippet?: string;
  rule?: string;
  started_at?: string;
  duration_ms?: number;
  review?: Review;
};
export type PipelineStage = {
  id: string;
  status: string;
  started_at?: string;
  finished_at?: string | null;
  duration_ms?: number;
  detail: string;
};
export type RunBrief = {
  finding_counts?: {raw:number;unique:number;duplicates:number;needs_review:number;false_positive:number;confirmed:number;test_issue:number;actionable:number};
  id: string;
  mode: "buggy" | "fixed" | "project" | "repository" | "unknown";
  report_url?: string;
  project_id?: string;
  label: string;
  status: string;
  decision: string;
  created_at: string;
  finished_at: string | null;
  source: SourceContext;
  check_count: number | null;
  findings_count: number | null;
  artifact_count: number | null;
  baseline_version: string;
  recorded_decision?: string;
  applicability?: { matches: boolean; reason: string };
  record_error?: string;
  count_note?: string;
  verification?: { state: string; label: string; last_verified_at?: string | null; last_valid?: boolean | null };
};
export type Repository = {
  id: string;
  repository: SourceContext["repository"];
  latest: RunBrief | null;
  run_count: number;
};
export type Run = RunBrief & {
  check_count: number;
  findings_count: number;
  artifact_count: number;
  job?: { id: string; state: string; attempt_id?: string | null; heartbeat_at?: string | null; recovery_error?: string | null } | null;
  review_provenance?:string;
  review_summary?: {
    non_actionable: number;
    pending: number;
    raw_failed: number;
  };
  workflow?: {
    model_batches?: {
      id: string;
      title: string;
      status: string;
      started_at?: string;
      finished_at?: string;
      connection?: { duration_ms?: number };
      ref?: string;
      input_ref?: string;
    }[];
  };
  completion?: {
    kind: string;
    complete: boolean;
    missing: string[];
    gaps?: import("./CoverageGaps").CoverageGap[];
    errors?: string[];
  };
  display_stages?: (PipelineStage & {
    title: string;
    tool: string;
    work: string;
  })[];
  test_plan?: Record<string, any>;
  universal_plan?: Record<string,any>;
  finding_page?: {offset:number;limit:number;total:number;has_more:boolean;state:string;query:string};
  test_plans?: { plan: Record<string, any>; execution: Record<string, any> }[];
  native_integration?: Record<string, any>;
  finished_at: string | null;
  baseline: {
    recipe?: string;
    exclusions?: { subject: string; reason: string }[];
    version: string;
    title: string;
    source: string;
    scope: string;
    digest: string;
    criteria: Criterion[];
  };
  suite_digest: string;
  target_digest: string;
  source_artifact?: string;
  project_inputs?: { path: string; ref: string }[];
  recipe_inputs?: { path: string; ref: string }[];
  results: Result[];
  findings: Finding[];
  artifacts: Artifact[];
  reasons: string[];
  limits: string[];
  integrity: boolean;
  pipeline?: PipelineStage[];
  check_runs?: {
    criterion_id: string;
    status: string;
    started_at: string;
    finished_at: string | null;
    duration_ms?: number | null;
    batch?: boolean;
  }[];
  current_activity?: {
    name: string;
    started_at: string;
    finished_at: string | null;
  };
  case_registration_ref?: string;
  inspections: Record<string, Inspection>;
  case_plans: Record<string, { subject: string; steps: string[] }>;
  layer_runs?: { layer: string; started_at: string; finished_at?: string }[];
  commands?: {
    name: string;
    argv: string[];
    started_at: string;
    finished_at?: string;
    exit_code: number | null;
    evidence_ref?: string;
  }[];
  layers: {
    id: string;
    name: string;
    status: string;
    count: number;
    failed: number;
  }[];
};
