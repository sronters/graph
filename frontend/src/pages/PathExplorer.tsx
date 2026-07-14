import cytoscape from "cytoscape";
import { GitBranch, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { StatusBadge } from "../components/StatusBadge";
import type { Finding } from "../types";

function PathGraph({ finding }: { finding: Finding }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const nodeIds = new Set<string>([finding.source_identity_id, finding.target_asset_id]);
    finding.path.forEach((step) => { nodeIds.add(step.actor_before); nodeIds.add(step.target_id); });
    const graph = cytoscape({ container: container.current, elements: [
      ...[...nodeIds].map((id) => ({ data: { id, label: id.split(":").slice(-1)[0] } })),
      ...finding.path.map((step) => ({ data: { id: `${finding.finding_id}:${step.position}`, source: step.actor_before, target: step.target_id, label: step.transition_type } })),
    ], style: [
      { selector: "node", style: { "background-color": "#0f766e", label: "data(label)", color: "#18312f", "font-size": 10, "text-valign": "bottom", "text-margin-y": 8 } },
      { selector: "edge", style: { width: 2, "line-color": "#d97706", "target-arrow-color": "#d97706", "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(label)", "font-size": 8 } },
    ], layout: { name: "breadthfirst", directed: true, padding: 24, spacingFactor: 1.25 } });
    return () => graph.destroy();
  }, [finding]);
  return <div className="path-graph" ref={container} role="img" aria-label={`Directed path from ${finding.source_identity_id} to ${finding.target_asset_id}`} />;
}

export function PathExplorer({ analysisId }: { analysisId: string | null }) {
  const [paths, setPaths] = useState<Finding[]>([]); const [selected, setSelected] = useState<Finding | null>(null); const [query, setQuery] = useState(""); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  useEffect(() => { if (!analysisId) return; setLoading(true); api.paths(analysisId).then((page) => { setPaths(page.items); setSelected(page.items[0] ?? null); }).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false)); }, [analysisId]);
  if (!analysisId) return <EmptyState title="Run an analysis first" detail="The path explorer renders only persisted findings, never a browser-submitted graph query." />;
  const filtered = paths.filter((path) => !query || `${path.source_identity_id} ${path.target_asset_id}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Evidence chain</p><h1>Path explorer</h1><p>One selected authorization path at a time, with ordered semantic and raw-edge provenance.</p></div><label className="search-field" htmlFor="path-search"><Search aria-hidden="true" /><span className="sr-only">Filter paths</span><input id="path-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Source or target" /></label></header>{loading && <LoadingState label="Loading ranked paths…" />}{error && <ErrorState message={error} />}{!loading && !error && !paths.length && <EmptyState title="No paths found" detail="The completed analysis did not rank a path under its configured bounds." />}{selected && <div className="path-layout"><section className="panel path-list"><h2>Ranked paths</h2>{filtered.map((path) => <button type="button" className={selected.finding_id === path.finding_id ? "path-row path-row--active" : "path-row"} onClick={() => setSelected(path)} key={path.finding_id}><GitBranch aria-hidden="true" /><span><strong>{path.source_identity_id}</strong><small>to {path.target_asset_id}</small></span><b>{(path.risk.path_risk * 100).toFixed(1)}</b></button>)}</section><section className="panel path-detail"><div className="panel-heading"><div><p className="eyebrow">Selected finding</p><h2>{selected.source_identity_id} → {selected.target_asset_id}</h2></div><StatusBadge status={selected.search.search_complete ? "verified" : "truncated"} /></div><PathGraph finding={selected} /><div className="score-line"><span>Relative path risk <strong>{(selected.risk.path_risk * 100).toFixed(1)}</strong></span><span>Transition cost <strong>{selected.risk.transition_cost.toFixed(2)}</strong></span><span>Criticality <strong>{selected.risk.criticality.toFixed(2)}</strong></span></div><h3>Ordered explanation</h3><ol className="steps">{selected.path.map((step) => <li key={step.position}><span className="step-index">{step.position + 1}</span><div><strong>{step.actor_before} uses {step.capability}</strong><p>{step.transition_type.replaceAll("_", " ")} toward {step.target_id}</p><small>Condition: {step.condition_state} · Evidence: {step.raw_evidence_edge_ids.join(", ")}</small></div></li>)}</ol>{selected.caveats.map((caveat) => <p className="notice" key={caveat}>{caveat}</p>)}</section></div>}</div>;
}
