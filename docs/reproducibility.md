# Reproducibility

## Clean environment

Clone the exact commit recorded by a run manifest on a machine with Git, Python 3.11/3.12, uv, Node 20+, and sufficient disk/RAM. Then run:

```bash
git clone https://github.com/sronters/graph.git
cd graph
git checkout <manifest.git_commit>
uv sync --frozen --all-extras
npm --prefix frontend ci
make quality
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

`uv.lock`, `package-lock.json`, configuration hashes, environment metadata, dataset hashes, and seeds pin the software/data inputs. Wall time and memory still depend on hardware.

## Regenerate data

For each profile, scale, and preregistered seed:

```bash
uv run graphtrust generate --profile saas_scaleup --scale small --seed 2750159 --output-root data/generated/final
uv run graphtrust validate-data --dataset data/generated/final/saas_scaleup/small/2750159/clean
uv run graphtrust validate-data --dataset data/generated/final/saas_scaleup/small/2750159/injected_low
uv run graphtrust validate-data --dataset data/generated/final/saas_scaleup/small/2750159/injected_mixed
```

Repeat with `regulated_finance` and `global_hybrid`, scales `small` and `medium`, and every seed in `configs/experiments.yaml`. Do not copy truth Parquet into an inference input. Compare generated `checksums.sha256` files byte-for-byte when verifying determinism.

## Regenerate results

Point `scripts/run_all_experiments.sh` at the generated root or invoke `graphtrust experiment` directly with the versioned registry. Runs are immutable and resumable; checksum-invalid partial directories are quarantined.

```bash
uv run graphtrust experiment --registry configs/experiments.yaml --data-root data/generated/final --workers 4 --resume
uv run python scripts/run_extended_evaluation.py --dataset data/generated/final/saas_scaleup/small/2750159/injected_mixed --output artifacts/extended/saas-small-2750159
uv run graphtrust report --runs artifacts/manifests --output artifacts/paper
uv run python scripts/generate_figures.py --runs artifacts/manifests --output artifacts/paper/figures
uv run python scripts/validate_traceability.py --artifacts artifacts
```

Use the Colab notebook for one large run per profile. Download its complete checkpoint/artifact directories; never report notebook console output without the saved manifests and checksums. `scripts/validate_traceability.py` rejects checksum mismatches and orphaned report sources.
