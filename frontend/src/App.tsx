import { lazy, Suspense, useEffect, useState } from "react";

import { api } from "./api/client";
import { EmptyState, ErrorState, LoadingState } from "./components/AsyncState";
import { Shell, type View } from "./components/Shell";
import { OverviewPage } from "./pages/OverviewPage";
import type { AnalysisJob, Dataset } from "./types";

const IdentityExplorer = lazy(() =>
  import("./pages/IdentityExplorer").then((module) => ({ default: module.IdentityExplorer })),
);
const PathExplorer = lazy(() =>
  import("./pages/PathExplorer").then((module) => ({ default: module.PathExplorer })),
);
const RemediationLab = lazy(() =>
  import("./pages/RemediationLab").then((module) => ({ default: module.RemediationLab })),
);
const ResearchResults = lazy(() =>
  import("./pages/ResearchResults").then((module) => ({ default: module.ResearchResults })),
);

export function App() {
  const [view, setView] = useState<View>("overview");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDatasets = async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api.datasets();
      setDatasets(page.items);
      setDatasetId((current) => current || page.items[0]?.dataset_id || "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unknown API error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadDatasets(); }, []);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try { setJob(await api.analysis(job.analysis_id)); } catch { /* next poll retries */ }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  const startAnalysis = async () => {
    if (!datasetId) return;
    setError("");
    try { setJob(await api.createAnalysis(datasetId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Analysis request failed"); }
  };

  const selectedDataset = datasets.find((dataset) => dataset.dataset_id === datasetId) ?? null;
  const analysisId = job?.status === "succeeded" ? job.analysis_id : null;

  let content;
  if (loading) content = <LoadingState label="Loading verified datasets…" />;
  else if (error && datasets.length === 0) content = <ErrorState message={error} retry={() => void loadDatasets()} />;
  else if (!selectedDataset) content = <EmptyState title="No datasets available" detail="Generate a SEIB-2026 dataset, then refresh this console." />;
  else if (view === "overview") content = (
    <OverviewPage datasets={datasets} selected={selectedDataset} onDataset={setDatasetId} job={job} onAnalyze={() => void startAnalysis()} error={error} />
  );
  else if (view === "identities") content = <IdentityExplorer analysisId={analysisId} />;
  else if (view === "paths") content = <PathExplorer analysisId={analysisId} />;
  else if (view === "remediation") content = <RemediationLab analysisId={analysisId} />;
  else content = <ResearchResults />;

  return (
    <Shell view={view} onView={setView}>
      <Suspense fallback={<LoadingState label="Loading investigation view…" />}>{content}</Suspense>
    </Shell>
  );
}
