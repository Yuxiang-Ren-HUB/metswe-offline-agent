# Replicate run (11/6, GPU handed to the paper by the user): base and gate v2 again on all 100 MetSWE tasks with the
# same code, conditions and sampling as run_all.sh/run2.sh, into new output dirs. Sampling is stochastic (t = 0.2), so
# this tests whether the gate v2 effect (fewer wrong patches, same resolved) survives a second draw. Rounds of growing
# --limit keep both conditions advancing together, so a partial run still gives a paired comparison.
export CUDA_VISIBLE_DEVICES="" LITELLM_LOCAL_MODEL_COST_MAP=True NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
unset ALL_PROXY all_proxy
cd /mnt/f/kaggle/gemma_agent/offline_paper/agent
LOG=/opt/offline/logs/run3.log
EXP=/opt/offline/exp
REPOS="pytroll/satpy pydata/xarray Unidata/MetPy NCAR/geocat-comp pytroll/pyresample ARM-DOE/pyart pySTEPS/pysteps wradlib/wradlib"

# never run two agents against one model at once
while pgrep -f "met_eval.py --condition|local_eval.py --submission" > /dev/null; do sleep 30; done

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
  for R in $REPOS; do run base base_r2 0 0 1 $LIM $R; done
  for R in $REPOS; do run gate gate2_r2 0 1 2 $LIM $R; done
done
echo "run3 done $(date '+%F %T')" >> $LOG
