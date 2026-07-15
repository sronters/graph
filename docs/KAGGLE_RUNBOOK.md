# GraphTrust large-run Kaggle runbook

Run the three profile notebooks separately in Kaggle with **Internet enabled**
and a CPU runtime exposing at least 20 GiB of available RAM. The workload does
not use a GPU. Kaggle's `/kaggle/working` is used for checkpoints and
`/kaggle/outputs` receives the verified archive and receipt.

If the notebook reports `Could not resolve host: github.com`, Internet is off in
the Kaggle session. Turn on Notebook **Settings → Internet** and restart the
session. If Internet cannot be enabled, attach a Kaggle Dataset mounted at
`/kaggle/input/graphtrust-source` containing `GraphTrust_NSRI_Main_Source.zip`
(or `GraphTrust_Kaggle_Source.zip`) and a text file
`GRAPHTRUST_SOURCE_COMMIT.txt` containing the expected `main`
commit. The notebook has an offline source fallback and records its mode in the
receipt.

## Notebooks and order

1. `notebooks/GraphTrust_Kaggle_Large_saas_scaleup.ipynb`
2. `notebooks/GraphTrust_Kaggle_Large_regulated_finance.ipynb`
3. `notebooks/GraphTrust_Kaggle_Large_global_hybrid.ipynb`

Open the notebook from the `main` branch, enable Internet in Notebook options,
and run every cell top-to-bottom. Each notebook clones the exact `main` commit,
installs the locked `uv` environment, runs the integration smoke test, creates
or reuses the deterministic 2.5-million-edge graph, and runs the bounded large
analysis from `configs/large.yaml`.

## Capacity gate and evidence rule

The first code cell refuses to continue below 20 GiB available RAM or 15 GiB
free working disk. This prevents a partial run from being mistaken for a
scalability result. Kaggle-specific receipts require:

```json
{
  "execution_platform": "kaggle",
  "is_kaggle": true,
  "profiles": [{"verified": true}]
}
```

The final cell copies `GraphTrust_large_<profile>_<seed>.zip` and
`GraphTrust_large_<profile>_<seed>_kaggle_receipt.json` into `/kaggle/outputs`.
Create a Kaggle notebook version before leaving the session so the output files
are retained. The archive hash in the receipt must match the downloaded ZIP.

Kaggle execution is hosted evidence only after the receipt and checksum are
saved. A local run, an interrupted session, or a notebook without a verified
receipt must not be cited as a large-scale result.
