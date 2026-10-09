#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 generate_dataset_v3.py
python3 compute_puf_metrics_v3.py
: > experiment_results_v3_parts.tmp
for S in A B C; do
  python3 experiment_v3.py --splits "$S" > "experiment_${S}_v3.log"
done
python3 assemble_v3_results.py
python3 fuzzy_commitment_v3.py
