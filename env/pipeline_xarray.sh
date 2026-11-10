#!/usr/bin/env bash
# Wait for the xarray image, probe it, then warm up and verify the post-cutoff xarray tasks.
export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 NO_PROXY=localhost,127.0.0.1
export CUDA_VISIBLE_DEVICES=""
D=/mnt/f/kaggle/gemma_agent/offline_paper
until grep -q "xarray: ok\|xarray: FAILED" /opt/offline/logs/build_xarray.log 2>/dev/null; do sleep 60; done
grep "xarray:" /opt/offline/logs/build_xarray.log | tail -1
bash $D/env/probe_imports.sh xarray 8 2>&1 | grep -v "^time="
cd $D/mining
echo "warmup $(date +%H:%M)"
nice -n 10 /opt/g4env/bin/python validate_tasks.py warmup --repo pydata/xarray --post-only > /opt/offline/logs/warm_xarray.log 2>&1
tail -2 /opt/offline/logs/warm_xarray.log
echo "verify $(date +%H:%M)"
nice -n 10 /opt/g4env/bin/python validate_tasks.py verify --repo pydata/xarray --post-only --concurrency 3 > /opt/offline/logs/verify_xarray.log 2>&1
tail -1 /opt/offline/logs/verify_xarray.log
