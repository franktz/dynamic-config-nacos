#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d dist ]]; then
  echo "dist directory not found. Run scripts/build_dist.sh first." >&2
  exit 1
fi

python3.12 -m twine check dist/*
