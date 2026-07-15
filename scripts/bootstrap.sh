#!/usr/bin/env bash
set -euo pipefail
uv sync --frozen --all-extras
npm --prefix frontend ci
