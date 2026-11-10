#!/usr/bin/env bash
D=/mnt/f/kaggle/gemma_agent/offline_paper/env
P=http://127.0.0.1:7897
for spec in "metpy|pytest<8" "geocat-comp|parameterized setuptools<81" "satpy|opencv-python-headless distributed"; do
  n=${spec%%|*}; pk=${spec#*|}
  for attempt in 1 2 3; do
    docker build --network host -f $D/docker/Dockerfile.extra --build-arg BASE=met-sandbox-$n:latest \
      --build-arg PKGS="$pk" --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P \
      -t met-sandbox-$n:latest $D/docker > /opt/offline/logs/extra2_$n.log 2>&1 && { echo "== $n: added $pk"; break; }
    echo "== $n: attempt $attempt failed"; sleep 20
  done
done
docker run --rm met-sandbox-metpy:latest python -c "import pytest; print('metpy pytest', pytest.__version__)"
