import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { api } from "./api/client";
import { App } from "./App";

vi.mock("cytoscape", () => ({ default: vi.fn(() => ({ destroy: vi.fn() })) }));
vi.mock("./api/client", () => ({
  api: {
    datasets: vi.fn(), createAnalysis: vi.fn(), analysis: vi.fn(), summary: vi.fn(),
    identities: vi.fn(), identity: vi.fn(), paths: vi.fn(), remediations: vi.fn(),
    experiments: vi.fn(), experimentMetrics: vi.fn(), experimentArtifacts: vi.fn(),
  },
}));

const dataset = {
  dataset_id: "seib:fixture", profile: "saas_scaleup", scale: "small", variant: "injected_mixed",
  seed: 104729, path: "data/fixture", warnings: [], counts: {
    human_identities: 220, non_human_identities: 450, resources: 900,
  },
};
const finding = {
  finding_id: "finding:1", method: "graphtrust", source_identity_id: "human:1",
  target_asset_id: "database:critical", risk: { path_risk: 0.91, transition_cost: 0.2, criticality: 0.95 },
  search: { search_complete: true, truncation_reason: null }, caveats: ["Relative risk is ordinal."],
  path: [{ position: 0, actor_before: "human:1", actor_after: "human:1", target_id: "database:critical",
    capability: "READS", transition_type: "DIRECT_ACCESS", condition_state: "TRUE",
    relative_exploitability: 0.9, raw_evidence_edge_ids: ["edge:1"] }],
};
const identity = {
  method: "graphtrust", node_id: "human:1", node_type: "HUMAN_IDENTITY", display_name: "Synthetic Engineer 1",
  provider: "INTERNAL", environment: "CORPORATE", department: "Engineering", identity_status: "ACTIVE",
  privilege_label: "LOW", critical_reach: 1, best_path: 0.9, path_diversity: 0.3, blast_radius: 0.2,
  control_weakness: 0.1, ztri: 71.5,
};

beforeEach(() => {
  vi.mocked(api.datasets).mockResolvedValue({ items: [dataset], total: 1, page: 1, page_size: 50 });
  vi.mocked(api.createAnalysis).mockResolvedValue({ analysis_id: "analysis:1", dataset_id: dataset.dataset_id,
    methods: ["graphtrust"], status: "succeeded", error: null });
  vi.mocked(api.summary).mockResolvedValue({ effective_edges: 12, rejected_semantic_edges: 1,
    methods: { graphtrust: { findings: 1, risky_starting_identities: 1, search_complete: true } } });
  vi.mocked(api.identities).mockResolvedValue({ items: [identity], total: 1, page: 1, page_size: 50 });
  vi.mocked(api.identity).mockResolvedValue({ scores: [identity], top_paths: [finding] });
  vi.mocked(api.paths).mockResolvedValue({ items: [finding], total: 1, page: 1, page_size: 50 });
  vi.mocked(api.remediations).mockResolvedValue({ recommendation_only: true, items: [{ plan_id: "plan:1",
    solver: "degree_greedy", status: "FEASIBLE", target_fraction: 0.8, removed_edge_ids: ["edge:1"],
    modeled_cost: 2, blocked_path_ids: ["finding:1"], residual_exposure: 0,
    protected_workflows_preserved: true, counterfactual_verified: true, optimality_gap: null,
    caveats: ["Recommendation only; no live permission changes are executed."] }] });
  vi.mocked(api.experiments).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 });
});

afterEach(() => cleanup());

test("dataset-to-identity-to-path-to-remediation flow uses API-backed state", async () => {
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByText("Exposure overview")).toBeInTheDocument();
  expect(screen.getByText("220")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Run analysis" }));
  expect(await screen.findByText("Detection comparison")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Identities" }));
  expect(await screen.findByText("Synthetic Engineer 1")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Inspect Synthetic Engineer 1" }));
  expect(await screen.findByText("Top reachable paths")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Paths" }));
  expect(await screen.findByText("Ordered explanation")).toBeInTheDocument();
  expect(screen.getByText(/Evidence: edge:1/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Remediation" }));
  await screen.findByText("Remediation lab");
  await user.selectOptions(screen.getByLabelText("Solver"), "degree_greedy");
  await user.selectOptions(screen.getByLabelText("Exposure target"), "0.8");
  await user.click(screen.getByRole("button", { name: "Calculate plans" }));
  const alternatives = await screen.findByRole("region", { name: "Remediation alternatives" });
  expect(within(alternatives).getByText("edge:1")).toBeInTheDocument();
  expect(within(alternatives).getByText(/counterfactual verified/)).toBeInTheDocument();
});

test("research results exposes a truthful empty state", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText("Exposure overview");
  await user.click(screen.getByRole("button", { name: "Research results" }));
  await waitFor(() => expect(screen.getByText("No verified experiment runs")).toBeInTheDocument());
});

test("overview has no automated WCAG violations", async () => {
  render(<App />);
  await screen.findByText("Exposure overview");
  const result = await axe.run(document.body, {
    rules: { "color-contrast": { enabled: false } },
  });
  expect(result.violations).toEqual([]);
});
