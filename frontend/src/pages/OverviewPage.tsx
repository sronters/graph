import { Activity, Boxes, KeyRound, Play, ShieldAlert, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { ErrorState, LoadingState } from "../components/AsyncState";
import { StatusBadge } from "../components/StatusBadge";
import type { AnalysisJob, Dataset } from "../types";

type Summary = {
  effective_edges: number;
  rejected_semantic_edges: number;
  methods: Record<string, { findings: number; risky_starting_identities: number; search_complete: boolean }>;
};

export function OverviewPage({ datasets, selected, onDataset, job, onAnalyze, error }: {
  datasets: Dataset[];
  selected: Dataset;
  onDataset: (id: string) => void;
  job: AnalysisJob | null;
  onAnalyze: () => void;
  error: string;
}) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryError, setSummaryError] = useState("");
  useEffect(() => {
    if (job?.status !== "succeeded") { setSummary(null); return; }
    api.summary(job.analysis_id).then((value) => setSummary(value as Summary)).catch((reason: Error) => setSummaryError(reason.message));
  }, [job]);

  const counts = selected.counts;
  const graphtrust = summary?.methods.graphtrust;
  const metrics = [
    { label: "Human identities", value: counts.human_identities ?? 0, icon: UsersRound },
    { label: "Non-human identities", value: counts.non_human_identities ?? 0, icon: KeyRound },
    { label: "Resources", value: counts.resources ?? 0, icon: Boxes },
    { label: "Risky starting identities", value: graphtrust?.risky_starting_identities ?? "—", icon: ShieldAlert },
    { label: "Ranked paths", value: graphtrust?.findings ?? "—", icon: Activity },
  ];

  return (
    <div className="page-stack">
      <header className="page-header">
        <div><p className="eyebrow">Current investigation</p><h1>Exposure overview</h1><p>Whole-identity reachability across typed, evidence-backed IAM transitions.</p></div>
        <div className="header-actions">
          <label htmlFor="dataset">Dataset</label>
          <select id="dataset" value={selected.dataset_id} onChange={(event) => onDataset(event.target.value)}>
            {datasets.map((dataset) => <option value={dataset.dataset_id} key={dataset.dataset_id}>{dataset.profile} · {dataset.scale} · {dataset.variant} · {dataset.seed}</option>)}
          </select>
          <button className="button" type="button" onClick={onAnalyze} disabled={job?.status === "queued" || job?.status === "running"}>
            <Play aria-hidden="true" />{job?.status === "running" ? "Analyzing…" : "Run analysis"}
          </button>
        </div>
      </header>

      <section className="context-strip" aria-label="Dataset provenance">
        <span><strong>{selected.profile.replaceAll("_", " ")}</strong> profile</span>
        <span>{selected.scale} scale</span><span>{selected.variant.replaceAll("_", " ")}</span>
        <span>seed {selected.seed}</span><StatusBadge status={job?.status ?? "generated"} />
      </section>
      {error && <p className="inline-error" role="alert">{error}</p>}

      <section className="metric-row" aria-label="Dataset and analysis counts">
        {metrics.map(({ label, value, icon: Icon }) => (
          <article className="metric" key={label}><Icon aria-hidden="true" /><span>{label}</span><strong>{typeof value === "number" ? value.toLocaleString() : value}</strong></article>
        ))}
      </section>

      {job?.status === "failed" && <ErrorState message={job.error ?? "Analysis failed without a stored error."} />}
      {(job?.status === "queued" || job?.status === "running") && <LoadingState label={`Analysis is ${job.status}. Results will update automatically.`} />}
      {summaryError && <ErrorState message={summaryError} />}
      {summary && (
        <div className="split-grid">
          <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Method parity</p><h2>Detection comparison</h2></div><StatusBadge status={Object.values(summary.methods).every((method) => method.search_complete) ? "fully_verified" : "truncated"} /></div>
            <div className="table-scroll"><table><thead><tr><th>Method</th><th>Findings</th><th>Risky identities</th><th>Search</th></tr></thead><tbody>{Object.entries(summary.methods).map(([method, result]) => <tr key={method}><th scope="row">{method.replaceAll("_", " ")}</th><td>{result.findings.toLocaleString()}</td><td>{result.risky_starting_identities.toLocaleString()}</td><td><StatusBadge status={result.search_complete ? "complete" : "truncated"} /></td></tr>)}</tbody></table></div>
          </section>
          <section className="panel"><p className="eyebrow">Semantic compiler</p><h2>Evidence health</h2><dl className="definition-list"><div><dt>Effective capability edges</dt><dd>{summary.effective_edges.toLocaleString()}</dd></div><div><dt>Rejected semantic edges</dt><dd>{summary.rejected_semantic_edges.toLocaleString()}</dd></div><div><dt>Dataset warnings</dt><dd>{selected.warnings.length}</dd></div></dl><p className="muted-copy">Unknown conditions and bounded searches remain visible in every path record.</p></section>
        </div>
      )}
    </div>
  );
}
