#!/usr/bin/env bash
# After round 2: apply the Py-ART / wradlib fixes, then re-verify their failed tasks.
D=/mnt/f/kaggle/gemma_agent/offline_paper
P=http://127.0.0.1:7897
while pgrep -f redo_round2.sh >/dev/null; do sleep 60; done
echo "round 2 done at $(date +%H:%M)"
cd $D/env/docker
for f in pyartfix wradlibfix; do
  for attempt in 1 2 3; do
    n=${f%fix}
    docker build --network host --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P \
      -f Dockerfile.$f -t met-sandbox-$n:latest . > /opt/offline/logs/$f.log 2>&1 && { echo "== $f ok"; break; }
    echo "== $f attempt $attempt failed"; sleep 20
  done
done
for r in ARM-DOE/pyart wradlib/wradlib; do python3 $D/mining/drop_failed.py $r; done
bash $D/env/run_validation.sh ARM-DOE/pyart wradlib/wradlib
