import { Search, UserRoundSearch } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { RiskBar } from "../components/RiskBar";
import { StatusBadge } from "../components/StatusBadge";
import type { Finding, Identity } from "../types";

export function IdentityExplorer({ analysisId }: { analysisId: string | null }) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [selected, setSelected] = useState<{ scores: Identity[]; top_paths: Finding[] } | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!analysisId) return;
    setLoading(true); setError("");
    api.identities(analysisId, query).then((page) => setIdentities(page.items)).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, [analysisId, query]);

  const inspect = async (nodeId: string) => {
    if (!analysisId) return;
    try { setSelected(await api.identity(analysisId, nodeId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to inspect identity"); }
  };

  if (!analysisId) return <EmptyState title="Run an analysis first" detail="The identity explorer consumes a completed, persisted analysis." />;
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Investigation</p><h1>Identity explorer</h1><p>Sort whole-identity risk into inspectable, evidence-backed components.</p></div><label className="search-field" htmlFor="identity-search"><Search aria-hidden="true" /><span className="sr-only">Search identities</span><input id="identity-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or stable ID" /></label></header>
    {loading && <LoadingState label="Loading identity scores…" />}{error && <ErrorState message={error} />}
    {!loading && !error && identities.length === 0 && <EmptyState title="No matching identities" detail="Change the search text or inspect another analysis." />}
    {identities.length > 0 && <div className="explorer-grid"><section className="panel table-panel"><div className="panel-heading"><div><p className="eyebrow">Ranked identities</p><h2>{identities.length} results</h2></div></div><div className="table-scroll"><table><thead><tr><th>Identity</th><th>Type</th><th>Provider</th><th>ZTRI</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{identities.map((identity) => <tr key={`${identity.method}:${identity.node_id}`}><th scope="row"><span>{identity.display_name}</span><small>{identity.node_id}</small></th><td>{identity.node_type.replaceAll("_", " ")}</td><td>{identity.provider}</td><td><strong>{identity.ztri.toFixed(1)}</strong></td><td><button className="table-action" type="button" onClick={() => void inspect(identity.node_id)} aria-label={`Inspect ${identity.display_name}`}><UserRoundSearch aria-hidden="true" /></button></td></tr>)}</tbody></table></div></section>
      <aside className="panel detail-panel" aria-live="polite">{selected ? <><div className="panel-heading"><div><p className="eyebrow">Identity detail</p><h2>{selected.scores[0].display_name}</h2><code>{selected.scores[0].node_id}</code></div><StatusBadge status={selected.scores[0].identity_status} /></div><p>{selected.scores[0].department} · {selected.scores[0].environment} · {selected.scores[0].privilege_label.toLowerCase()} privilege</p><div className="risk-stack"><RiskBar label="Critical reach" value={selected.scores[0].critical_reach * 100} /><RiskBar label="Best path" value={selected.scores[0].best_path * 100} /><RiskBar label="Path diversity" value={selected.scores[0].path_diversity * 100} /><RiskBar label="Blast radius" value={selected.scores[0].blast_radius * 100} /><RiskBar label="Control weakness" value={selected.scores[0].control_weakness * 100} /></div><h3>Top reachable paths</h3>{selected.top_paths.length ? <ol className="compact-list">{selected.top_paths.slice(0, 5).map((path) => <li key={path.finding_id}><span>{path.target_asset_id}</span><strong>{(path.risk.path_risk * 100).toFixed(1)}</strong></li>)}</ol> : <p className="muted-copy">No ranked paths for this identity.</p>}</> : <EmptyState title="Choose an identity" detail="Select a ranked row to inspect score decomposition and top paths." />}</aside>
    </div>}</div>;
}
