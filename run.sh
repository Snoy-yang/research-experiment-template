#!/usr/bin/env bash
set -euo pipefail
PY="../../env/research/python.exe"
[ -f "$PY" ] || PY="python"
echo "[1/2] pytest"; "$PY" -m pytest -q tests/
echo "[2/2] run";    "$PY" src/main.py --config configs/default.yaml | tee logs/last_run.log
echo "结果：results/metrics.json"
