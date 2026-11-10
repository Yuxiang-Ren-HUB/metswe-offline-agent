#!/usr/bin/env bash
export CUDA_VISIBLE_DEVICES=""
D=/mnt/f/kaggle/gemma_agent/offline_paper
while pgrep -f redo_xarray2.sh >/dev/null; do sleep 60; done
echo "xarray round done at $(date +%H:%M)"; tail -1 /opt/offline/logs/verify_xarray3.log
cd $D/mining
nice -n 10 /opt/g4env/bin/python final_reverify.py 4 > /opt/offline/logs/final_reverify.log 2>&1
echo "final pass done at $(date +%H:%M)"; tail -1 /opt/offline/logs/final_reverify.log
