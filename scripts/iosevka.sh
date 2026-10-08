#!/usr/bin/env bash
# Iosevka working copies live on the WSL filesystem (fast builds), not under /mnt/c.
#   iosevka.sh setup [workdir]                         clone pinned tag + npm ci
#   iosevka.sh build <plans.toml> <plan> <out.ttf> [workdir]
# Run inside the pixi env (provides node).
set -euo pipefail
TAG=v34.9.0
COMMIT=2487637bb71f41b2a66134afd9faa6c316e5a438
cmd=$1; shift

case $cmd in
setup)
  W=${1:-$HOME/maxocr-work/iosevka}
  if [ ! -d "$W" ]; then
    git clone -q --depth 1 --branch $TAG https://github.com/be5invis/Iosevka.git "$W"
  fi
  [ "$(git -C "$W" rev-parse HEAD)" = $COMMIT ] || { echo "Iosevka commit mismatch in $W"; exit 1; }
  [ -d "$W/node_modules" ] || (cd "$W" && npm ci --no-audit --no-fund >/dev/null)
  echo "ok $W"
  ;;
build)
  plans=$(realpath "$1"); plan=$2; out=$(realpath -m "$3"); W=${4:-$HOME/maxocr-work/iosevka}
  cp "$plans" "$W/private-build-plans.toml"
  (cd "$W" && npm run build -- "ttf-unhinted::$plan" >/tmp/iosevka-$plan.log 2>&1) \
    || { tail -30 /tmp/iosevka-$plan.log; exit 1; }
  mkdir -p "$(dirname "$out")"
  cp "$W/dist/$plan/TTF-Unhinted/$plan-Regular.ttf" "$out"
  echo "ok $out"
  ;;
*) echo "unknown command $cmd"; exit 2 ;;
esac
