#!/usr/bin/env bash
# Run the Windows font survey in capped, resumable batches until every face is done.
# Stops at the first failing batch: retrying a deterministic failure only burns CPU
# (and a forgotten retry loop once ran alongside a second copy of this script).
cd "$(dirname "$0")/.."
for i in $(seq 1 20); do
  ~/.pixi/bin/pixi run timeout -s KILL 300 python -u scripts/font_survey.py --max-faces 60 > /tmp/survey_batch.log 2>&1
  status=$?
  grep -v '^OMP\|timestamp seems' /tmp/survey_batch.log
  bash scripts/kill_workers.sh > /dev/null
  if [ $status -ne 0 ]; then echo "batch failed (exit $status); stopping"; exit $status; fi
  grep -q "running 0" /tmp/survey_batch.log && break
done
