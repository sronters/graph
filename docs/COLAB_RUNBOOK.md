# GraphTrust large-run Colab runbook

Run the three profile notebooks separately. Each notebook persists its dataset
and immutable analysis under `MyDrive/GraphTrustLarge`, so a disconnected
runtime can be resumed by running the same notebook again from the first cell.

## Before starting

1. Merge PR #2 into `main` so the notebook clones the final reviewed code.
2. In Colab, choose a CPU high-RAM runtime. A GPU is not used by this workload.
3. Ensure at least 20 GiB of available RAM and 15 GiB of free Google Drive
   space. The notebook checks both before generating the large graph.

## Run order

Run every cell from top to bottom in each notebook:

1. `GraphTrust_Colab_Large_saas_scaleup.ipynb`
2. `GraphTrust_Colab_Large_regulated_finance.ipynb`
3. `GraphTrust_Colab_Large_global_hybrid.ipynb`

The preflight cell first checks the exact large-generation plan and runs the
experiment-runner integration test. Generation writes the deterministic
2.5-million-edge graph to Drive. Analysis uses the frozen bounded scalability
budget in `configs/large.yaml`: at most 30 hash-selected sources, 50
hash-selected critical targets, depth 6, and 150 retained paths. This measures
large-graph generation, semantic compilation, bounded search, memory, and
runtime. It is not an exhaustive large-graph recall experiment.

## Successful completion

The final cell downloads two files:

- `GraphTrust_large_<profile>_2750159.zip`
- `download_receipt.json`

A result is usable only when `large_run_receipt.json` records
`is_google_colab: true`, the profile records `verified: true`, and the ZIP hash
matches `archive_sha256` in `download_receipt.json`. Keep all three ZIPs and all
three receipts; do not rename or edit their contents before verification.
