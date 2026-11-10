#!/usr/bin/env bash
# Rebuild the final sandbox image of one MetSWE repository in one step (network needed; run inside WSL/Linux).
#   bash build_image.sh pyart            -> met-sandbox-pyart:latest, then met-sandbox-pyart:warm
# The layer order below is read from `docker history` of the images used in the paper (built 2026-10-13); the original
# rounds were spread over build_met_images.sh, fix_and_probe.sh, extras_round2.sh, pipeline_B.sh, redo_*.sh.
# Package versions are resolved at build time, so compare the result with locks/<repo>.txt (pip freeze of the paper's
# images): bash build_image.sh --check pyart
# Needs: Docker; the competition's base image swebench-sandbox:latest (env/setup_wsl.sh); the task snapshots for the
# warm-up (mining/validate_tasks.py snapshot); a proxy in PROXY if the network needs one.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
D="$HERE/docker"
P="${PROXY:-}"
ARGS=(--network host)
[ -n "$P" ] && ARGS+=(--build-arg HTTP_PROXY=$P --build-arg HTTPS_PROXY=$P --build-arg http_proxy=$P --build-arg https_proxy=$P)

if [ "${1:-}" = "--check" ]; then
  n=$2
  diff <(docker run --rm met-sandbox-$n:warm pip freeze | sort) <(sort "$HERE/locks/$n.txt") && echo "$n: identical to the paper's image" || echo "$n: package versions differ (lines above)"
  exit 0
fi

n=$1
declare -A REPO=([metpy]=Unidata/MetPy [geocat-comp]=NCAR/geocat-comp [pyart]=ARM-DOE/pyart [pyresample]=pytroll/pyresample
                 [satpy]=pytroll/satpy [wradlib]=wradlib/wradlib [pysteps]=pySTEPS/pysteps [xarray]=pydata/xarray)
# extra packages, applied in this order (each one Dockerfile.extra layer)
declare -A EXTRA=([metpy]="pytest<8" [geocat-comp]="geocat-datafiles distributed|parameterized setuptools<81"
                  [pyart]="mda-xdrlib" [pyresample]="versioneer" [satpy]="appdirs hdf5plugin pygac hvplot|opencv-python-headless distributed"
                  [wradlib]="hatch-fancy-pypi-readme hatch-requirements-txt" [pysteps]="setuptools<81"
                  [xarray]="h5py pytz polars flox sparse pooch|pandas<3 pytest-asyncio")
declare -A FIX=([pyart]=Dockerfile.pyartfix [wradlib]=Dockerfile.wradlibfix [geocat-comp]=Dockerfile.geocatfix)
[ -n "${REPO[$n]:-}" ] || { echo "unknown repository $n (one of: ${!REPO[*]})"; exit 1; }

echo "== $n: base layer (Dockerfile.met, req_$n.txt)"
docker build "${ARGS[@]}" --build-arg REQ=req_$n.txt -f "$D/Dockerfile.met" -t met-sandbox-$n:latest "$D"
IFS='|' read -ra steps <<< "${EXTRA[$n]}"
for pk in "${steps[@]}"; do
  echo "== $n: extra packages: $pk"
  docker build "${ARGS[@]}" -f "$D/Dockerfile.extra" --build-arg BASE=met-sandbox-$n:latest --build-arg PKGS="$pk" -t met-sandbox-$n:latest "$D"
done
if [ -n "${FIX[$n]:-}" ]; then
  echo "== $n: fix layer ${FIX[$n]}"
  docker build "${ARGS[@]}" -f "$D/${FIX[$n]}" -t met-sandbox-$n:latest "$D"
fi
echo "== $n: warm-up (runs every task's tests once with network so data caches are baked in; commits :warm)"
cd "$HERE/../benchmark" 2>/dev/null || cd "$HERE/../mining"
python validate_tasks.py warmup --repo "${REPO[$n]}"
echo "== $n: done; compare versions with: bash $0 --check $n"
