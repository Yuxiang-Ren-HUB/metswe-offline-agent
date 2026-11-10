#!/usr/bin/env bash
D=/mnt/f/kaggle/gemma_agent/offline_paper
P=http://127.0.0.1:7897
for attempt in 1 2 3; do
  docker build --network host -f $D/env/docker/Dockerfile.extra --build-arg BASE=met-sandbox-satpy:latest \
    --build-arg PKGS="appdirs hdf5plugin pygac hvplot" --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P \
    -t met-sandbox-satpy:latest $D/env/docker > /opt/offline/logs/extra_satpy.log 2>&1 && { echo "satpy extras added"; break; }
  sleep 20
done
python3 $D/mining/drop_failed.py pytroll/satpy
bash $D/env/run_validation.sh pytroll/satpy
