#!/usr/bin/env bash
# After pipeline B finishes: re-verify the failed tasks of repos whose images got more packages.
D=/mnt/f/kaggle/gemma_agent/offline_paper
while pgrep -f pipeline_B.sh >/dev/null; do sleep 60; done
echo "pipeline B done at $(date +%H:%M)"
for r in Unidata/MetPy NCAR/geocat-comp pytroll/satpy; do
  python3 $D/mining/drop_failed.py $r
done
bash $D/env/run_validation.sh Unidata/MetPy NCAR/geocat-comp pytroll/satpy
