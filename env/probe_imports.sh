#!/usr/bin/env bash
# Collect (not run) the test files of a few tasks per repository inside its image, offline, and list
# missing modules so the requirement files can be completed before the warm-up.
# Usage: bash probe_imports.sh <repo-short-name> [n_tasks]
n=$1; k=${2:-4}
img=met-sandbox-$n:latest
cd /mnt/f/kaggle/gemma_agent/offline_paper/mining
python3 - "$n" "$k" > /tmp/probe_$n.txt <<'PY'
import json, sys
n, k = sys.argv[1], int(sys.argv[2])
T = [json.loads(l) for l in open("tasks_unvalidated.jsonl")]
T = [t for t in T if t["repo"].split("/")[1].lower() == n]
T.sort(key=lambda t: t["merged_at"], reverse=True)
for t in T[:k]:
    print(t["instance_id"], " ".join(t["test_files"]))
PY
docker rm -f probe_$n >/dev/null 2>&1
docker run -d --network none --name probe_$n $img sleep infinity >/dev/null
while read -r id files; do
  docker exec -w / probe_$n bash -c "rm -rf /workspace && mkdir -p /workspace"  # /workspace is the default cwd
  docker cp /opt/offline/snapshots/$id.tgz probe_$n:/tmp/s.tgz
  docker exec -w /workspace probe_$n bash -c "tar -xzf /tmp/s.tgz && pip install -q -e . --no-deps --no-build-isolation >/dev/null 2>&1; python -m pytest --collect-only -q -p no:cacheprovider $files 2>&1" \
    | grep -oE "No module named '[^']+'|cannot import name '[^']+'" | sort | uniq -c | sed "s/^/$id: /"
done < /tmp/probe_$n.txt
docker rm -f probe_$n >/dev/null
