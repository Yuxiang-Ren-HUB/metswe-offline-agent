#!/usr/bin/env bash
# Build one sandbox image per repository from Dockerfile.met (network only at build time).
# Usage: bash build_met_images.sh [repo-short-name ...]   (default: all, largest task count first)
#        FORCE=1 bash build_met_images.sh pyart            (rebuild even if the image exists)
set -uo pipefail
cd "$(dirname "$0")/docker"
P=http://127.0.0.1:7897
NAMES=${*:-"satpy geocat-comp metpy pyart pyresample wradlib pysteps cfgrib xarray"}
for n in $NAMES; do
  if [ -z "${FORCE:-}" ] && docker image inspect met-sandbox-$n:latest >/dev/null 2>&1; then echo "== $n: exists"; continue; fi
  echo "== $n: building"
  t0=$(date +%s)
  ok=0
  for attempt in 1 2 3; do  # the proxy occasionally drops TLS connections during large pip downloads
    # host network so the build can reach the Windows proxy at 127.0.0.1 (mirrored networking)
    if docker build --network host --build-arg REQ=req_$n.txt \
         --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P --build-arg http_proxy=$P --build-arg https_proxy=$P \
         -f Dockerfile.met -t met-sandbox-$n:latest . > /opt/offline/logs/image_$n.log 2>&1; then
      ok=1; break
    fi
    echo "== $n: attempt $attempt failed, retrying"; sleep 30
  done
  if [ $ok = 1 ]; then echo "== $n: ok in $(( $(date +%s) - t0 ))s"
  else echo "== $n: FAILED (see /opt/offline/logs/image_$n.log)"; tail -15 /opt/offline/logs/image_$n.log; fi
done
docker images | grep met-sandbox
