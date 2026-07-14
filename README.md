# GraphTrust

GraphTrust is a reproducible research system for explainable, whole-identity graph analysis of multi-hop IAM exposure. It normalizes synthetic multi-provider authorization records into a typed effective-capability graph, ranks potential paths to critical assets, and evaluates recommendation-only remediations under declared business constraints.

The claim under test is deliberately narrow: on SEIB-2026 synthetic enterprise graphs, typed multi-hop analysis may make injected authorization-exposure evidence more reviewable at a fixed analyst budget relative to the implemented B0–B3 research baselines, while constrained remediation may reduce modeled exposure at an auditable business-removal cost. GraphTrust does **not** prove exploitability or compromise, estimate incident probability, describe every commercial IAM product, inspect live tenants, collect credentials, or make permission changes.

## Architecture

Raw Parquet IAM records and truth-separated scenario labels flow through validation and provider-aware semantic compilation. NetworkX is the reference backend; igraph provides a parity-checked scalable backend. B0–B3 and GraphTrust share one analysis protocol. Saved findings feed truth-separated metrics, constrained remediation, an immutable experiment registry, a versioned FastAPI service, and a React investigation interface. Every derived edge retains its source edge IDs and named compiler rule.

## Install

Python 3.11 or 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 20+ are required for local development.

```bash
uv sync --all-extras
npm --prefix frontend ci
uv run graphtrust --help
```

## Quick correctness run

```bash
uv run graphtrust generate --profile saas_scaleup --scale small --seed 104729 --output-root data/generated/quick
uv run graphtrust validate-data --dataset data/generated/quick/saas_scaleup/small/104729/injected_mixed
uv run graphtrust analyze --dataset data/generated/quick/saas_scaleup/small/104729/injected_mixed --methods graphtrust
uv run graphtrust remediate --analysis artifacts/latest --solvers constraint_generation --targets 0.90
```

The generator creates paired `clean`, `injected_low`, `injected_mixed`, and `remediated_truth` variants. Truth files are excluded from inference and joined only during evaluation.

## Experiments and evidence

Run the pre-specified small/medium matrix only after generating every configured dataset:

```bash
bash scripts/run_all_experiments.sh
uv run graphtrust report --runs artifacts/manifests --output artifacts/paper
uv run python scripts/generate_figures.py --runs artifacts/manifests --output artifacts/paper/figures
uv run python scripts/validate_traceability.py --artifacts artifacts
```

Each immutable run directory contains `manifest.json`, `metrics.json`, `findings.jsonl`, `runtime.json`, `environment.json`, and `checksums.sha256`. Reports retain their source run IDs. See [methodology](docs/methodology.md) and [reproducibility](docs/reproducibility.md).

For hosted execution, open [GraphTrust_Colab.ipynb](notebooks/GraphTrust_Colab.ipynb) in Google Colab, enable the high-RAM runtime for large graphs, set `REPO_URL`, then run cells in order. Large profile runs are intentionally explicit and checkpointed; this repository does not treat an unexecuted notebook as empirical evidence.

## API and dashboard

```bash
uv run graphtrust serve --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Open `http://localhost:5173`; OpenAPI is at `http://localhost:8000/docs`. Or run `docker compose up --build` and use `http://localhost:8080`. The interface reads actual API artifacts and exposes overview, identity, path, remediation, and research-result views. It cannot apply changes to an IAM system.

## Data, safety, and limitations

Source code is Apache-2.0. SEIB-2026 datasets are deterministic synthetic outputs distributed under the repository license and must not be represented as observations of real organizations. Use external inputs only when sanitized and authorized. Do not operationalize a recommendation without independent review.

Key limitations are synthetic representativeness, normalized rather than exhaustive provider semantics, static snapshots, bounded Top-K paths, ordinal risk weights, modeled business costs, and scenario-family-dependent ground truth. Reachability is potential authorization exposure—not evidence that misuse occurred. See [limitations](docs/limitations.md) and [threat model](docs/threat_model.md).

## Verification and citation

```bash
make quality
uv run pytest tests/performance -m performance
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Use [CITATION.cff](CITATION.cff) and cite the exact dataset manifest and experiment run IDs used in a result. The current evidence status is recorded in the [verification ledger](docs/verification_status.md) and [research brief](docs/research_brief.md).

The short reviewer-facing reproduction path is [README_REPRODUCE_HEADLINE.md](README_REPRODUCE_HEADLINE.md). It defines Precision/Recall@K, cluster bootstrap units, depth stress, and remediation replication without treating prepared Colab notebooks as executed evidence.
