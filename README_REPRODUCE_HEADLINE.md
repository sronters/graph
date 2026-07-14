# Reproduce the headline result

The headline endpoint is exact-path ranking under an analyst review budget.
It is not exhaustive recall.

```powershell
uv sync --frozen --all-extras
uv run python scripts/run_depth_stress.py --dataset-root data/generated --depths 1,2,3,4,5,6 --output results/depth_stress.csv
uv run python scripts/build_final_results.py --runs artifacts/final_matrix --artifact-root artifacts --output artifacts/final_paper/generated
uv run python scripts/generate_figures.py --runs artifacts/final_matrix --output artifacts/final_paper/figures
```

The evaluator emits `precision_at_{5,10,20,50}` and
`recall_at_{5,10,20,50}` after truth is joined. The report builder collapses
paired variants to `(profile, seed)` cluster means before confidence intervals.
The checked-in `results/review_budget_summary.csv` records the operator's
review-budget audit values; it must be replaced by the complete generated
summary when all 225 raw run directories are available.

For remediation replication:

```powershell
uv run python scripts/run_remediation_replication.py --dataset-root data/generated --targets 0.50,0.70,0.80,0.90,0.95
```

Large Colab notebooks are prepared launchers and require an authenticated
high-RAM Colab receipt before their runtime/memory numbers can be cited.
