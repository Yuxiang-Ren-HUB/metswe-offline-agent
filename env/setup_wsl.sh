#!/usr/bin/env bash
# One-time environment for the offline-agent experiments, inside WSL2 Ubuntu 24.04.
# Run as root from Windows:   wsl -d Ubuntu-24.04 -u root -- bash /mnt/f/kaggle/gemma_agent/offline_paper/env/setup_wsl.sh [step...]
# Steps are idempotent and can be run one at a time:  apt docker venv model image smoke
set -euo pipefail

G=/mnt/f/kaggle/gemma_agent                 # Windows-side competition files
VENV=/opt/g4env                             # Python 3.12 env for vLLM + swegemma
MODELS=/opt/models                          # model weights on the ext4 disk (fast loading)
PROXY_PORT=${PROXY_PORT:-7897}              # Clash on the Windows host
STEPS=${*:-"apt docker venv model image smoke"}

log() { echo -e "\n=== $*"; }

step_proxy() {
  # With networkingMode=mirrored the Windows proxy is reachable at 127.0.0.1; otherwise use the host IP.
  local host=127.0.0.1
  if ! (exec 3<>/dev/tcp/$host/$PROXY_PORT) 2>/dev/null; then
    host=$(ip route show default | awk '{print $3; exit}')
  fi
  export http_proxy=http://$host:$PROXY_PORT https_proxy=http://$host:$PROXY_PORT
  export HTTP_PROXY=$http_proxy HTTPS_PROXY=$https_proxy NO_PROXY=localhost,127.0.0.1
  log "proxy -> $http_proxy"
  curl -sS -m 15 -o /dev/null -w "github %{http_code}\n" https://github.com || echo "WARNING: no internet through proxy"
}

step_apt() {
  log "apt packages"
  apt-get update -q
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q git pigz curl ca-certificates build-essential \
    python3.12 python3.12-venv python3.12-dev docker.io
}

step_docker() {
  log "docker daemon"
  mkdir -p /etc/systemd/system/docker.service.d
  if [ -n "${http_proxy:-}" ]; then   # image builds need the proxy; containers at run time are network_mode=none
    printf '[Service]\nEnvironment="HTTP_PROXY=%s" "HTTPS_PROXY=%s" "NO_PROXY=localhost,127.0.0.1"\n' \
      "$http_proxy" "$https_proxy" > /etc/systemd/system/docker.service.d/proxy.conf
  fi
  systemctl daemon-reload || true
  systemctl enable --now docker || service docker start
  docker info --format 'docker {{.ServerVersion}}, storage {{.Driver}}'
  # let the default (non-root) user run docker
  local u; u=$(getent passwd 1000 | cut -d: -f1 || true)
  [ -n "$u" ] && usermod -aG docker "$u" && echo "added $u to docker group"
}

step_venv() {
  log "python env at $VENV"
  [ -d $VENV ] || python3.12 -m venv $VENV
  $VENV/bin/pip install -q -U pip uv
  # vLLM pins its own torch build; install it from PyPI first, then the competition packages on top
  $VENV/bin/uv pip install --python $VENV/bin/python "vllm==0.19.1"
  $VENV/bin/uv pip install --python $VENV/bin/python \
    $G/wheelhouse/swegemma-0.2.7-py3-none-any.whl \
    $G/wheelhouse/adk_submission-0.2.11-py3-none-any.whl \
    $G/wheelhouse/adk_eval_core-0.1.0-py3-none-any.whl \
    $G/wheelhouse/google_adk-1.36.1-py3-none-any.whl \
    $G/wheelhouse/google_genai-2.11.0-py3-none-any.whl \
    $G/wheelhouse/compressed_tensors-0.15.0.1-py3-none-any.whl \
    pytest litellm pyyaml pandas
  # version check only: do not initialise CUDA here (the GPU may be busy with other work)
  $VENV/bin/python -c "import vllm, torch, swegemma; print('vllm', vllm.__version__, 'torch', torch.__version__, 'built for cuda', torch.version.cuda)"
}

step_model() {
  log "copy model weights to ext4"
  mkdir -p $MODELS
  for m in gemma-4-12b-it-qat-w4a16-ct; do
    [ -f $MODELS/$m/model.safetensors ] || rsync -a --info=progress2 $G/models/$m/ $MODELS/$m/
  done
  du -sh $MODELS/*
}

step_image() {
  log "build the official sandbox image (needs network at build time only)"
  docker image inspect swebench-sandbox:latest >/dev/null 2>&1 || \
    docker build -t swebench-sandbox:latest -f $G/data/docker/Dockerfile.sandbox $G/data/docker
  docker images | grep -E "swebench-sandbox|met-sandbox" || true
}

step_smoke() {
  log "vLLM smoke test with 12B (gpu-memory-utilization 0.85: the 4090 also drives the display)"
  nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
  export VLLM_WORKER_MULTIPROC_METHOD=spawn VLLM_NO_USAGE_STATS=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  $VENV/bin/python -m vllm.entrypoints.openai.api_server --model $MODELS/gemma-4-12b-it-qat-w4a16-ct \
    --served-model-name gemma-4-12b-it --host 127.0.0.1 --port 8000 --max-model-len 32768 \
    --gpu-memory-utilization 0.85 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
    > /tmp/vllm_smoke.log 2>&1 &
  local pid=$!
  for i in $(seq 1 120); do curl -s localhost:8000/v1/models >/dev/null && break; sleep 5; done
  curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"gemma-4-12b-it","messages":[{"role":"user","content":"Reply with the word ok."}],"max_tokens":20}' | head -c 600; echo
  nvidia-smi --query-gpu=memory.used --format=csv
  kill $pid; wait $pid 2>/dev/null || true
  tail -5 /tmp/vllm_smoke.log
}

step_proxy   # every run needs it (apt, pip, docker build)
for s in $STEPS; do "step_$s"; done
