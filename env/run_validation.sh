#!/usr/bin/env bash
# Warm up and verify the given repositories in order (one pipeline; run several in parallel for speed).
# Usage: bash run_validation.sh <owner/repo> [<owner/repo> ...]
export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 NO_PROXY=localhost,127.0.0.1
export CUDA_VISIBLE_DEVICES=""
cd /mnt/f/kaggle/gemma_agent/offline_paper/mining
for r in "$@"; do
  n=$(basename $r | tr 'A-Z' 'a-z')
  echo "######## $r  $(date +%H:%M)"
  nice -n 10 /opt/g4env/bin/python validate_tasks.py warmup --repo $r > /opt/offline/logs/warm_$n.log 2>&1
  tail -2 /opt/offline/logs/warm_$n.log
  nice -n 10 /opt/g4env/bin/python validate_tasks.py verify --repo $r --concurrency 3 > /opt/offline/logs/verify_$n.log 2>&1
  tail -1 /opt/offline/logs/verify_$n.log
done
