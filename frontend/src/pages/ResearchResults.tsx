import { Download, FileCheck2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { StatusBadge } from "../components/StatusBadge";
import type { Experiment } from "../types";

type RunResult = Experiment & { detection?: Record<string, number>; artifactCount?: number };

export function ResearchResults() {
  const [runs, setRuns] = useState<RunResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    api.experiments().then(async (page) => {
      const resolved = await Promise.all(page.items.map(async (run) => {
        const [metrics, artifacts] = await Promise.all([api.experimentMetrics(run.run_id), api.experimentArtifacts(run.run_id)]);
        return { ...run, detection: metrics.detection, artifactCount: artifacts.artifacts.length };
      })); setRuns(resolved);
    }).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, []);
  if (loading) return <LoadingState label="Verifying experiment manifests and metrics…" />;
  if (error) return <ErrorState message={error} />;
  if (!runs.length) return <EmptyState title="No verified experiment runs" detail="Run the experiment matrix to populate artifact-backed research results." />;
  const maxF1 = Math.max(...runs.map((run) => run.detection?.scenario_f1 ?? 0), 1e-9);
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Reproducible evidence</p><h1>Research results</h1><p>Every plotted value is loaded from a checksum-verified immutable run directory.</p></div><StatusBadge status="artifact_backed" /></header><section className="panel"><div className="panel-heading"><div><p className="eyebrow">Detection comparison</p><h2>Scenario-level F1 by run</h2></div></div><div className="bar-chart" role="img" aria-label="Scenario F1 values for verified experiment runs">{runs.map((run) => { const value = run.detection?.scenario_f1 ?? 0; return <div className="chart-row" key={run.run_id}><span>{run.method}</span><progress max={maxF1} value={value} aria-label={`${run.method} scenario F1 ${value.toFixed(3)}`} /><strong>{value.toFixed(3)}</strong></div>; })}</div></section><section className="panel table-panel"><div className="panel-heading"><div><p className="eyebrow">Manifest inventory</p><h2>Verified runs</h2></div><span>{runs.length} immutable runs</span></div><div className="table-scroll"><table><thead><tr><th>Run</th><th>Dataset</th><th>Method</th><th>Scenario F1</th><th>Artifacts</th><th><span className="sr-only">Download</span></th></tr></thead><tbody>{runs.map((run) => <tr key={run.run_id}><th scope="row"><FileCheck2 aria-hidden="true" /><code>{run.run_id}</code></th><td><small>{run.dataset_id}</small></td><td>{run.method}</td><td>{run.detection?.scenario_f1.toFixed(3) ?? "—"}</td><td>{run.artifactCount}</td><td><button className="table-action" type="button" aria-label={`Artifact inventory for ${run.run_id}`} title="Artifacts are available through the API"><Download aria-hidden="true" /></button></td></tr>)}</tbody></table></div></section></div>;
}
