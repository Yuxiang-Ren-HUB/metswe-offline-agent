# Ablations (11/7), both fixed before any task ran; same code, sampling, budgets (28 calls, 14 min) and task order as
# run3.sh, into new output dirs:
#   gateprompt  the gate v2 prompt (conditions/gate) with the mechanical gate off: no repair, no checks, no rejection.
#               Differs from base only in the prompt paragraph, and from gate v2 only in the gate.
#   gate2sh     gate v2 with one prompt sentence added (conditions/gate_sh): create /tmp/repro.py with run_command,
#               because write_file/edit_file only write inside /workspace. Everything else as gate v2.
# Rounds of growing --limit keep both conditions advancing together, so a partial run still gives a paired comparison.
export CUDA_VISIBLE_DEVICES="" LITELLM_LOCAL_MODEL_COST_MAP=True NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
unset ALL_PROXY all_proxy
cd /mnt/f/kaggle/gemma_agent/offline_paper/agent
LOG=/opt/offline/logs/run4.log
EXP=/opt/offline/exp
REPOS="pytroll/satpy pydata/xarray Unidata/MetPy NCAR/geocat-comp pytroll/pyresample ARM-DOE/pyart pySTEPS/pysteps wradlib/wradlib"

# never run two agents against one model at once
while pgrep -f "met_eval.py --condition|local_eval.py --submission|local_eval11.py --submission" > /dev/null; do sleep 30; done

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
  for R in $REPOS; do run gate gateprompt 0 0 1 $LIM $R; done
  for R in $REPOS; do run gate_sh gate2sh 0 1 2 $LIM $R; done
done
echo "run4 done $(date '+%F %T')" >> $LOG
