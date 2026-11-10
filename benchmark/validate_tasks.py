"""Execution-validate candidate tasks with the official grader (run inside WSL, in /opt/g4env).

  python validate_tasks.py snapshot --repo pytroll/satpy --post-only        # needs network
  python validate_tasks.py warmup   --repo pytroll/satpy                    # needs network; commits :warm image
  python validate_tasks.py verify   --repo pytroll/satpy --concurrency 6    # air-gapped, official verify_task

A task is valid when the empty patch is NOT resolved and the gold patch is resolved twice in a row
(flaky tests excluded). Because the grader runs every test file touched by test_patch in full and needs
exit code 0, a task whose test files already contain failures under Python 3.13 + current dependencies
is dropped here rather than being unsolvable later.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks_unvalidated.jsonl"
WORK = Path(os.environ.get("OFFLINE_WORK", "/opt/offline"))
SNAP = WORK / "snapshots"
RESULTS = HERE / "validation.jsonl"
DATA = Path("/mnt/f/kaggle/gemma_agent/data")
EMPTY_WHEELS = WORK / "empty_wheels"  # keep the competition's fastapi-ecosystem wheels out of these images


def sh(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r


def load(args):
    tasks = [json.loads(l) for l in TASKS.read_text(encoding="utf-8").splitlines()]
    if args.repo:
        tasks = [t for t in tasks if t["repo"] == args.repo]
    if args.exclude:
        tasks = [t for t in tasks if t["repo"] not in set(args.exclude.split(","))]
    if args.post_only:
        tasks = [t for t in tasks if t["post_cutoff"]]
    if args.ids:
        tasks = [t for t in tasks if t["instance_id"] in set(args.ids.split(","))]
    return tasks[: args.limit] if args.limit else tasks


def image_for(repo, warm=True):
    return f"met-sandbox-{repo.split('/')[1].lower()}" + (":warm" if warm else ":latest")


# ------------------------------------------------------------------ snapshots
MIRRORS = WORK / "mirrors"


def ensure_mirror(repo):
    """One full local mirror per repository, so each snapshot is a local fetch instead of a download."""
    dest = MIRRORS / (repo.split("/")[1] + ".git")
    if dest.exists():
        return dest
    MIRRORS.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):  # large transfers through the proxy occasionally drop (GnuTLS recv error)
        sh(f"rm -rf {dest}.tmp", check=False)
        r = sh(f"git -c http.version=HTTP/1.1 clone -q --mirror https://github.com/{repo}.git {dest}.tmp", check=False)
        if r.returncode == 0:
            sh(f"mv {dest}.tmp {dest}")
            return dest
        print(f"mirror {repo} attempt {attempt + 1} failed: {r.stderr[-300:]}", flush=True)
        time.sleep(20)
    raise RuntimeError(f"could not mirror {repo}")


def make_snapshot(t):
    """Repository at base_commit with the last 30 commits of history; no later commits can leak in."""
    out = SNAP / f"{t['instance_id']}.tgz"
    if out.exists():
        return out
    mirror = ensure_mirror(t["repo"])
    with tempfile.TemporaryDirectory(dir=WORK) as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        sh("git init -q && git config user.email a@b && git config user.name snap", cwd=repo)
        sh(f"git fetch -q --depth 30 file://{mirror} {t['base_commit']}", cwd=repo)
        sh("git checkout -q -b main FETCH_HEAD && git reflog expire --expire=now --all && git gc -q --prune=now", cwd=repo)
        head = sh("git rev-parse HEAD", cwd=repo).stdout.strip()
        assert head == t["base_commit"], (head, t["base_commit"])
        sh(f"tar -czf {out} -C {repo} .")
    return out


# ------------------------------------------------------------------ warm-up (networked)
def warmup(tasks, repo):
    """Run every task's tests once with network so download caches (pooch, open-radar-data...) are baked in."""
    img = image_for(repo, warm=False)
    name = f"warm_{repo.split('/')[1].lower()}"
    proxy = os.environ.get("https_proxy", "")
    env = f"-e HTTP_PROXY={proxy} -e HTTPS_PROXY={proxy} -e http_proxy={proxy} -e https_proxy={proxy}" if proxy else ""
    sh(f"docker rm -f {name}", check=False)
    # host network: reaches the Windows proxy at 127.0.0.1 (mirrored networking); proxy vars are cleared at commit
    sh(f"docker run -d --network host {env} --name {name} {img} sleep infinity")
    def installed():
        return {d["name"].lower() for d in json.loads(sh(f"docker exec {name} pip list --format=json").stdout)}
    before = installed()
    try:
        if repo == "pySTEPS/pysteps":  # tests read radar sample data from the separate pysteps-data repository
            sh(f"docker exec {name} bash -c 'git clone -q --depth 1 https://github.com/pySTEPS/pysteps-data /opt/pysteps-data'")
        for t in tasks:
            snap = make_snapshot(t)
            d = f"/warm/{t['instance_id']}"
            sh(f"docker exec {name} mkdir -p {d}")
            sh(f"docker cp {snap} {name}:/tmp/s.tgz && docker exec {name} tar -xzf /tmp/s.tgz -C {d}")
            for kind in ("patch", "test_patch"):
                p = Path(tempfile.mkstemp(suffix=".diff")[1])
                p.write_text(t[kind], encoding="utf-8")
                sh(f"docker cp {p} {name}:/tmp/{kind}.diff")
                sh(f"docker exec -w {d} {name} git apply /tmp/{kind}.diff", check=False)
                p.unlink()
            sh(f"docker exec -w {d} {name} pip install -q -e . --no-deps --no-build-isolation", check=False)
            files = " ".join(t["test_files"])
            # run whole files (no -x) so every test's downloads get cached
            r = sh(f"docker exec -w {d} {name} timeout 900 python -m pytest -q -p no:cacheprovider {files}", check=False)
            print(f"warm {t['instance_id']}: exit {r.returncode}", flush=True)
            # undo the editable install: a stale finder pointing at /warm would shadow /workspace later
            new = sorted(installed() - before)
            if new:
                sh(f"docker exec {name} pip uninstall -y -q {' '.join(new)}", check=False)
        sh(f"docker exec {name} rm -rf /warm /tmp/s.tgz /tmp/patch.diff /tmp/test_patch.diff")
        clear = " ".join(f'--change "ENV {v}="' for v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"))
        sh(f"docker commit {clear} {name} {image_for(repo)}")
    finally:
        sh(f"docker rm -f {name}", check=False)


# ------------------------------------------------------------------ verification (air-gapped, official grader)
async def verify_one(t, sem, attempt_labels=("empty", "gold1", "gold2")):
    from adk_submission import ModelRegistry
    from swegemma.config import EvalConfig
    from swegemma.harness.verification import verify_task
    from swegemma.models.task import Task
    from swegemma.sandbox.docker import ContainerConfig, ContainerManager

    task = Task(instance_id=t["instance_id"], repo=t["repo"], base_commit=t["base_commit"],
                problem_statement=t["problem_statement"], patch=t["patch"], test_patch=t["test_patch"],
                created_at=t["merged_at"])
    config = EvalConfig(tasks_path=TASKS, snapshots_dir=SNAP, results_dir=WORK / "verify_results",
                        submission_dir=WORK / "none", models=ModelRegistry(), image=image_for(t["repo"]),
                        wheels_dir=EMPTY_WHEELS)
    docker = ContainerManager(ContainerConfig(image=image_for(t["repo"]), network_mode="none"))
    rec = {"instance_id": t["instance_id"], "repo": t["repo"], "post_cutoff": t["post_cutoff"]}
    async with sem:
        for label in attempt_labels:
            patch = "" if label == "empty" else t["patch"]
            t0 = time.time()
            try:
                res = await verify_task(docker, config, task, SNAP / f"{t['instance_id']}.tgz", agent_patch=patch)
                rec[label] = {"resolved": bool(res.resolved), "exit": res.test_exit_code, "sec": round(time.time() - t0),
                              "error": res.error, "tail": (res.test_output or "")[-1500:]}
            except Exception as e:
                rec[label] = {"resolved": False, "exit": None, "sec": round(time.time() - t0), "error": repr(e)}
            if label == "empty" and rec[label]["resolved"]:
                break  # tests already pass without the fix: invalid, no need to run gold
    rec["valid"] = (not rec["empty"]["resolved"]) and all(rec.get(k, {}).get("resolved") for k in ("gold1", "gold2"))
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"{t['instance_id']}: valid={rec['valid']} " +
          " ".join(f"{k}={rec[k]['resolved']}" for k in attempt_labels if k in rec), flush=True)
    return rec


async def verify(tasks, concurrency):
    done = set()
    if RESULTS.exists():
        done = {json.loads(l)["instance_id"] for l in RESULTS.read_text(encoding="utf-8").splitlines()}
    todo = [t for t in tasks if t["instance_id"] not in done]
    for t in todo:
        make_snapshot(t)
    sem = asyncio.Semaphore(concurrency)
    recs = await asyncio.gather(*(verify_one(t, sem) for t in todo))
    print(f"valid {sum(r['valid'] for r in recs)} / {len(recs)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["snapshot", "warmup", "verify"])
    ap.add_argument("--repo")
    ap.add_argument("--exclude", help="comma-separated repos to skip, e.g. pydata/xarray")
    ap.add_argument("--ids")
    ap.add_argument("--post-only", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()
    for d in (WORK, SNAP, EMPTY_WHEELS):
        d.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("KAGGLE_SANDBOX_DIR", str(DATA / "sandbox"))
    tasks = load(a)
    print(f"{len(tasks)} tasks selected", flush=True)
    if a.step == "snapshot":
        for t in tasks:
            print(make_snapshot(t), flush=True)
    elif a.step == "warmup":
        assert a.repo, "--repo is required for warmup (one image per repository)"
        warmup(tasks, a.repo)
    else:
        asyncio.run(verify(tasks, a.concurrency))


if __name__ == "__main__":
    sys.exit(main())
