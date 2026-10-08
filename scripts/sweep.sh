#!/usr/bin/env bash
# Run sweep levels one at a time, each hard-capped, cleaning up workers after each.
#   bash scripts/sweep.sh 0 0.5 1.0            (sweep bank, 180 s cap per level)
#   BANK=validation CAP=420 bash scripts/sweep.sh 0.5
cd "$(dirname "$0")/.."
for s in "$@"; do
  ~/.pixi/bin/pixi run timeout -s KILL "${CAP:-180}" python -u scripts/sweep.py --bank "${BANK:-sweep}" --severity "$s"
  echo "exit code: $?"
  bash scripts/kill_workers.sh
done
