#!/usr/bin/env bash
export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 NO_PROXY=localhost,127.0.0.1
export CUDA_VISIBLE_DEVICES=""
D=/mnt/f/kaggle/gemma_agent/offline_paper
P=http://127.0.0.1:7897
for attempt in 1 2 3; do
  docker build --network host -f $D/env/docker/Dockerfile.extra --build-arg BASE=met-sandbox-xarray:latest \
    --build-arg PKGS="h5py pytz polars flox sparse pooch" --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P \
    -t met-sandbox-xarray:latest $D/env/docker > /opt/offline/logs/extra_xarray.log 2>&1 && { echo "xarray extras added"; break; }
  sleep 20
done
bash $D/env/probe_imports.sh xarray 10 2>&1 | grep -v "^time="
python3 $D/mining/drop_failed.py pydata/xarray
cd $D/mining
echo "warmup $(date +%H:%M)"
nice -n 10 /opt/g4env/bin/python validate_tasks.py warmup --repo pydata/xarray --post-only > /opt/offline/logs/warm_xarray2.log 2>&1
echo "verify $(date +%H:%M)"
nice -n 10 /opt/g4env/bin/python validate_tasks.py verify --repo pydata/xarray --post-only --concurrency 4 > /opt/offline/logs/verify_xarray2.log 2>&1
tail -1 /opt/offline/logs/verify_xarray2.log
