#!/usr/bin/env bash
# Kill every MaxOCR harness Python process in WSL.
# Parents first: multiprocessing.Pool respawns workers that die while the parent lives.
ENV_PY="pixi-envs/maxocr-"

for p in $(pgrep -f "$ENV_PY.*/bin/python [^-]"); do kill -9 "$p" 2>/dev/null; done
sleep 1
for p in $(pgrep -f "$ENV_PY.*(spawn_main|resource_tracker)"); do kill -9 "$p" 2>/dev/null; done
sleep 1

left=$(pgrep -fc "$ENV_PY")
if [ "$left" -eq 0 ]; then
  echo "No MaxOCR processes running."
else
  echo "Still running ($left):"
  pgrep -fa "$ENV_PY"
fi
