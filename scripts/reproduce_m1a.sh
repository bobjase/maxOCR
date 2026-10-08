#!/usr/bin/env bash
# R45: one command reproduces the M1a artifacts. Run from WSL:
#   bash scripts/reproduce_m1a.sh
# Every heavy step is time-capped and followed by a worker cleanup. Total ~45-60 min on the
# reference machine. Outputs land in out/ (sweep, validation, probe, report).
set -euo pipefail
cd "$(dirname "$0")/.."
PIXI=~/.pixi/bin/pixi
step() { echo; echo "=== $* ==="; }
capped() { local cap=$1; shift; $PIXI run timeout -s KILL "$cap" "$@"; bash scripts/kill_workers.sh > /dev/null; }

step "environment and pinned data"
$PIXI install
bash scripts/fetch_vendor.sh
$PIXI run bash scripts/iosevka.sh setup
$PIXI run bash scripts/iosevka.sh build iosevka/private-build-plans.toml MaxOCRCand out/fonts/Iosevka-Regular.ttf

step "tests (unit + risky checks)"
capped 300 pytest -q tests

step "baseline sweep (sweep bank, 2,000 lines x 6 fonts x 2 suites per level)"
capped 240 python -u scripts/sweep.py --clean --severity 0
for s in 0 0.1 0.2 0.3 0.4 0.5 1.0 1.5; do
  capped 240 python -u scripts/sweep.py --severity "$s"
done

step "operating point (Section 7, relative rule)"
capped 120 python scripts/operating_point.py
OP=$($PIXI run python -c "import json; print(json.load(open('out/report/operating_point.json'))['severity'])")
echo "operating point severity: $OP"

step "validation bank at the operating point (5,000 lines)"
capped 600 python -u scripts/sweep.py --bank validation --severity "$OP"

step "clusters, baseline table, reliability curve"
capped 300 python scripts/m1a_validation.py --severity "$OP"
capped 300 python scripts/m1a_report.py

step "R40b probe classifier"
for f in OCR-A OCR-B Iosevka JetBrainsMono IBMPlexMono SourceCodePro; do
  capped 400 python -u scripts/probe.py --font "$f" --severity "$OP" > /dev/null
done
capped 400 python -u scripts/probe.py --font Iosevka --clean > /dev/null

step "R40 pixel distance"
capped 900 python -u scripts/r40.py

echo; echo "M1a artifacts reproduced in out/. Timing sheet: python scripts/timing.py (separate, ~10 min)."
