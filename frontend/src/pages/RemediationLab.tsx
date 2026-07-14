import { CheckCircle2, FlaskConical, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { StatusBadge } from "../components/StatusBadge";

type Plan = {
  plan_id: string;
  solver: string;
  status: string;
  target_fraction: number;
  removed_edge_ids: string[];
  modeled_cost: number;
  blocked_path_ids: string[];
  residual_exposure: number;
  protected_workflows_preserved: boolean;
  counterfactual_verified: boolean;
  optimality_gap: number | null;
  caveats: string[];
};

export function RemediationLab({ analysisId }: { analysisId: string | null }) {
  const [solver, setSolver] = useState("constraint_generation");
  const [target, setTarget] = useState(0.9);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  if (!analysisId) return <EmptyState title="Run an analysis first" detail="Remediation candidates are computed against a completed finding set." />;

  const calculate = async () => {
    setLoading(true); setError("");
    try { const result = await api.remediations(analysisId, solver, target); setPlans(result.items as unknown as Plan[]); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Remediation failed"); }
    finally { setLoading(false); }
  };

  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Constrained optimization</p><h1>Remediation lab</h1><p>Compare counterfactually verified edge-removal plans under protected workflow constraints.</p></div></header><div className="recommendation-banner"><FlaskConical aria-hidden="true" /><div><strong>Recommendation only</strong><p>No live permissions or identity-provider settings are changed.</p></div></div><section className="panel control-panel"><label htmlFor="solver">Solver<select id="solver" value={solver} onChange={(event) => setSolver(event.target.value)}><option value="degree_greedy">Degree greedy (B4)</option><option value="risk_greedy">Risk greedy (B5)</option><option value="min_cut">Weighted min-cut</option><option value="constraint_generation">Constraint generation</option></select></label><label htmlFor="target">Exposure target<select id="target" value={target} onChange={(event) => setTarget(Number(event.target.value))}><option value={0.8}>Block 80%</option><option value={0.9}>Block 90%</option><option value={1}>Block 100%</option></select></label><button className="button" type="button" onClick={() => void calculate()}><ShieldCheck aria-hidden="true" />Calculate plans</button></section>{loading && <LoadingState label="Solving and verifying counterfactual reachability…" />}{error && <ErrorState message={error} />}{!loading && !error && plans.length === 0 && <EmptyState title="No plan calculated" detail="Choose a solver and exposure target, then calculate a recommendation." />}{plans.length > 0 && <section className="plan-grid" aria-label="Remediation alternatives">{plans.slice(0, 5).map((plan) => <article className="panel plan-card" key={`${plan.plan_id}:${plan.target_fraction}`}><div className="panel-heading"><div><p className="eyebrow">{plan.solver.replaceAll("_", " ")}</p><h2>{Math.round(plan.target_fraction * 100)}% target</h2></div><StatusBadge status={plan.status} /></div><dl className="plan-stats"><div><dt>Modeled cost</dt><dd>{plan.modeled_cost.toFixed(2)}</dd></div><div><dt>Edge changes</dt><dd>{plan.removed_edge_ids.length}</dd></div><div><dt>Paths blocked</dt><dd>{plan.blocked_path_ids.length}</dd></div><div><dt>Residual exposure</dt><dd>{(plan.residual_exposure * 100).toFixed(1)}%</dd></div></dl><h3>Proposed removals</h3><ul className="edge-list">{plan.removed_edge_ids.slice(0, 8).map((edge) => <li key={edge}><code>{edge}</code></li>)}</ul><div className="verification-line"><CheckCircle2 aria-hidden="true" /><span>Workflows {plan.protected_workflows_preserved ? "preserved" : "not preserved"}; counterfactual {plan.counterfactual_verified ? "verified" : "not verified"}</span></div><p className="muted-copy">Solver guarantee: {plan.optimality_gap === null ? "No finite optimality gap reported" : `${plan.optimality_gap.toFixed(3)} gap`}.</p></article>)}</section>}</div>;
}
