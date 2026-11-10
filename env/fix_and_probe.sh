#!/usr/bin/env bash
# Add missing packages to existing images, build the images that failed, then probe every image again.
set -uo pipefail
D=/mnt/f/kaggle/gemma_agent/offline_paper/env
P=http://127.0.0.1:7897
extra() {  # extra <repo> <packages...>
  local n=$1; shift
  for attempt in 1 2 3; do
    if docker build --network host -f $D/docker/Dockerfile.extra --build-arg BASE=met-sandbox-$n:latest \
         --build-arg PKGS="$*" --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P \
         -t met-sandbox-$n:latest $D/docker > /opt/offline/logs/extra_$n.log 2>&1; then
      echo "== $n: added $*"; return; fi
    sleep 20
  done
  echo "== $n: FAILED adding $*"; tail -5 /opt/offline/logs/extra_$n.log
}
extra pyart mda-xdrlib
extra geocat-comp geocat-datafiles distributed
extra pyresample versioneer
bash $D/build_met_images.sh satpy wradlib
for n in metpy pyart pyresample geocat-comp satpy wradlib pysteps cfgrib; do
  echo "##### probe $n"; bash $D/probe_imports.sh $n 6 2>&1 | grep -v "^time="
done
