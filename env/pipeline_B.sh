#!/usr/bin/env bash
D=/mnt/f/kaggle/gemma_agent/offline_paper/env
P=http://127.0.0.1:7897
for spec in "wradlib|hatch-fancy-pypi-readme hatch-requirements-txt" "pysteps|setuptools<81"; do
  n=${spec%%|*}; pk=${spec#*|}
  for attempt in 1 2 3; do
    docker build --network host -f $D/docker/Dockerfile.extra --build-arg BASE=met-sandbox-$n:latest \
      --build-arg PKGS="$pk" --build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P \
      -t met-sandbox-$n:latest $D/docker > /opt/offline/logs/extra_$n.log 2>&1 && { echo "== $n: added $pk"; break; }
    sleep 20
  done
done
bash $D/probe_imports.sh wradlib 4 2>&1 | grep -v "^time="
bash $D/probe_imports.sh pysteps 2 2>&1 | grep -v "^time="
bash $D/run_validation.sh Unidata/MetPy NCAR/geocat-comp ARM-DOE/pyart pytroll/pyresample wradlib/wradlib pySTEPS/pysteps ecmwf/cfgrib
