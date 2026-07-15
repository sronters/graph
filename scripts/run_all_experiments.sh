#!/usr/bin/env bash
set -euo pipefail

PROFILES=(saas_scaleup regulated_finance global_hybrid)
FINAL_SEEDS=(2750159 3681131 4264387 5000011 6500027)
VARIANTS=clean,injected_low,injected_mixed,remediated_truth

uv sync --all-extras --frozen

for profile in "${PROFILES[@]}"; do
  for scale in small medium; do
    for seed in "${FINAL_SEEDS[@]}"; do
      destination="data/generated/${profile}/${scale}/${seed}"
      if [[ ! -d "${destination}/injected_mixed" ]]; then
        uv run graphtrust generate \
          --profile "${profile}" \
          --scale "${scale}" \
          --seed "${seed}" \
          --variants "${VARIANTS}"
      fi
    done
  done
done

uv run graphtrust experiment \
  --registry configs/experiments.yaml \
  --workers "${GRAPHTRUST_WORKERS:-1}" \
  --resume

if [[ "${GRAPHTRUST_INCLUDE_LARGE:-0}" == "1" ]]; then
  for profile in "${PROFILES[@]}"; do
    seed="${FINAL_SEEDS[0]}"
    if [[ ! -d "data/generated/${profile}/large/${seed}/injected_mixed" ]]; then
      uv run graphtrust generate \
        --profile "${profile}" \
        --scale large \
        --seed "${seed}" \
        --variants "${VARIANTS}"
    fi
  done
fi

uv run graphtrust report --runs artifacts/manifests --output artifacts/paper
