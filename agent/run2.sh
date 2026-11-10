# Second queue (11/3). Gate v1 and kp+gate v1 stop at 47 tasks (their failure analysis motivated gate v2; these
# 47 tasks are the development set). Remaining work, in rounds of growing --limit so all conditions advance
# together: gate v2 on all 100 tasks, and base / kp completed to 100 (met_eval resumes from results.jsonl).
export CUDA_VISIBLE_DEVICES="" LITELLM_LOCAL_MODEL_COST_MAP=True NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
unset ALL_PROXY all_proxy
cd /mnt/f/kaggle/gemma_agent/offline_paper/agent
LOG=/opt/offline/logs/run2.log
EXP=/opt/offline/exp
REPOS="pytroll/satpy pydata/xarray Unidata/MetPy NCAR/geocat-comp pytroll/pyresample ARM-DOE/pyart pySTEPS/pysteps wradlib/wradlib"

# the last task of the first queue is still running; never run two agents against one model at once
while pgrep -f "met_eval.py --condition" > /dev/null; do sleep 30; done

run() {  # condition-dir out-name KP GATE GATE_VERSION limit repo
  N=$(echo $7 | cut -d/ -f2 | tr A-Z a-z)
  mkdir -p /opt/offline/tmp_$N
  echo "=== $(date '+%F %T') round $6 $2 $7" >> $LOG
  OFFLINE_KP=$3 OFFLINE_GATE=$4 OFFLINE_GATE_VERSION=$5 TMPDIR=/opt/offline/tmp_$N nice -n 10 /opt/g4env/bin/python met_eval.py \
    --condition $1 --repo $7 --limit $6 --api-base http://127.0.0.1:11434/v1 --served gemma4-31b-qat \
    --out $EXP/31b_$2 2>&1 | grep -E '^\[|Error|Traceback' >> $LOG
  docker ps -q --filter ancestor=met-sandbox-$N:warm | xargs -r docker rm -f > /dev/null 2>&1
}

for LIM in 3 6 10 15 20 30 45; do
  for R in $REPOS; do run gate gate2 0 1 2 $LIM $R; done
  if [ $LIM -ge 15 ]; then
    for R in $REPOS; do run base base 0 0 1 $LIM $R; done
    for R in $REPOS; do run kp kp 1 0 1 $LIM $R; done
  fi
done
pkill -f "nvidia-smi --query-gpu=timestamp"
echo "run2 done $(date '+%F %T')" >> $LOG
