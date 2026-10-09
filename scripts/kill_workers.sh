#!/usr/bin/env bash
# Kill every MaxOCR harness process in WSL: Python drivers and workers, and Iosevka (node/verda) builds.
# Parents first: multiprocessing.Pool respawns workers that die while the parent lives.
# Drivers started through `pixi run python ...` show up as plain "python scripts/x.py", without the
# environment path, so they are matched by script location too.
ENV_PY="pixi-envs/maxocr-"
DRIVER="^python (-u )?(scripts|scratch)/[A-Za-z0-9_]+\.py"   # anchored: never match a wrapper shell
BUILD="maxocr-work/iosevka.*verda"

for p in $(pgrep -f "$DRIVER"); do kill -9 "$p" 2>/dev/null; done
for p in $(pgrep -f "$ENV_PY.*/bin/python [^-]"); do kill -9 "$p" 2>/dev/null; done
sleep 1
for p in $(pgrep -f "$ENV_PY.*(spawn_main|resource_tracker)"); do kill -9 "$p" 2>/dev/null; done
for p in $(pgrep -f "spawn_main|resource_tracker"); do kill -9 "$p" 2>/dev/null; done
for p in $(pgrep -f "$BUILD"); do kill -9 "$p" 2>/dev/null; done
sleep 1

left=$(pgrep -fc "$DRIVER|$ENV_PY|spawn_main|$BUILD")
if [ "$left" -eq 0 ]; then
  echo "No MaxOCR processes running."
else
  echo "Still running ($left):"
  pgrep -fa "$DRIVER|$ENV_PY|spawn_main|$BUILD"
fi
