#!/bin/bash
# usage: scripts/run_load_tier.sh <1k|5k|10k> <think_seconds>   (server must be running on :8000)
set -e; cd "$(dirname "$0")/.."; T=$1; THINK=${2:-1}
(cd load_tests && TIER=$T THINK=$THINK k6 run --quiet --summary-export=../evidence/load/${T}_raw.json k6_50k_load.js) || true
python3 scripts/load_evidence.py $T $THINK
