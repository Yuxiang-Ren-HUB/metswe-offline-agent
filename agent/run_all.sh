# Full experiment: 4 conditions x tasks_exp100 with 31B (Ollama). Rounds of growing --limit so that all four
# conditions advance together (met_eval resumes from results.jsonl); a partial run still gives a paired comparison.
export CUDA_VISIBLE_DEVICES="" LITELLM_LOCAL_MODEL_COST_MAP=True NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
unset ALL_PROXY all_proxy
cd /mnt/f/kaggle/gemma_agent/offline_paper/agent
LOG=/opt/offline/logs/run_all.log
EXP=/opt/offline/exp
REPOS="pytroll/satpy pydata/xarray Unidata/MetPy NCAR/geocat-comp pytroll/pyresample ARM-DOE/pyart pySTEPS/pysteps wradlib/wradlib"

# GPU power/memory every 30 s for the time/energy table
nvidia-smi --query-gpu=timestamp,power.draw,memory.used,utilization.gpu --format=csv,noheader -l 30 >> $EXP/gpu_power.csv &
SAMPLER=$!

for LIM in 3 6 10 15 20 30 45; do
  for C in base kp gate kp_gate; do
    case $C in base) K=0 G=0;; kp) K=1 G=0;; gate) K=0 G=1;; kp_gate) K=1 G=1;; esac
    for R in $REPOS; do
      N=$(echo $R | cut -d/ -f2 | tr A-Z a-z)
      mkdir -p /opt/offline/tmp_$N
      echo "=== $(date '+%F %T') round $LIM $C $R" >> $LOG
      OFFLINE_KP=$K OFFLINE_GATE=$G TMPDIR=/opt/offline/tmp_$N nice -n 10 /opt/g4env/bin/python met_eval.py \
        --condition $C --repo $R --limit $LIM --api-base http://127.0.0.1:11434/v1 --served gemma4-31b-qat \
        --out $EXP/31b_$C 2>&1 | grep -E '^\[|Error|Traceback' >> $LOG
      docker ps -q --filter ancestor=met-sandbox-$N:warm | xargs -r docker rm -f > /dev/null 2>&1
    done
  done
done
kill $SAMPLER
echo "run_all done $(date '+%F %T')" >> $LOG
