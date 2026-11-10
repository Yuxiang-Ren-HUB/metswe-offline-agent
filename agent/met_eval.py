"""Run one experiment condition on the atmospheric-science benchmark (WSL, /opt/g4env).

  OFFLINE_KP=0/1 OFFLINE_GATE=0/1 python met_eval.py --condition kp_gate --repo pytroll/satpy \
      --api-base http://127.0.0.1:11434/v1 --served gemma4-31b-qat --out /opt/offline/exp/31b_kp_gate

One process per repository: each repository has its own sandbox image (met-sandbox-<repo>:warm), and swegemma
caches unpacked wheels in $TMPDIR under a fixed name, so TMPDIR is set per process by the caller.
Budget: 28 tool calls, 14 min wall clock (the 8-min Kaggle budget scaled by the measured 1.7x local slowdown),
240 s per command. Each finished task appends a JSON line (with the patch) to <out>/results.jsonl; reruns resume.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import local_extensions  # noqa: E402  (must patch SwegemmaContext before the evaluator is built)

local_extensions.install()

import yaml  # noqa: E402
from google.adk.agents.context_cache_config import ContextCacheConfig  # noqa: E402
from google.adk.apps._configs import EventsCompactionConfig  # noqa: E402
from swegemma.config import EvalConfig, build_submission_limits  # noqa: E402
from swegemma.evaluate import Evaluator  # noqa: E402
from swegemma.models.discovery import validate_single_declared_model  # noqa: E402
from swegemma.models.registry import setup_gemma_model_registry  # noqa: E402
from swegemma.models.task import load_tasks  # noqa: E402

MINING = HERE.parent / "mining"
SNAP = Path("/opt/offline/snapshots")
EMPTY_WHEELS = Path("/opt/offline/empty_wheels")

ap = argparse.ArgumentParser()
ap.add_argument("--condition", required=True, help="base | kp | gate | kp_gate (directory under conditions/)")
ap.add_argument("--repo", required=True)
ap.add_argument("--tasks-file", default=str(MINING / "tasks_exp100.jsonl"))
ap.add_argument("--api-base", required=True)
ap.add_argument("--served", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--ids", default="", help="comma-separated instance ids")
ap.add_argument("--minutes", type=float, default=14.0)
ap.add_argument("--calls", type=int, default=28)
a = ap.parse_args()

sub, out = HERE / "conditions" / a.condition, Path(a.out)
out.mkdir(parents=True, exist_ok=True)
EMPTY_WHEELS.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("OFFLINE_LOG", str(out / "offline_events.jsonl"))
# the harness needs sandbox/setup.py (fast-path test config); the official data ships it
os.environ.setdefault("KAGGLE_SANDBOX_DIR", "/mnt/f/kaggle/gemma_agent/data/sandbox")
if ":11434" in a.api_base:  # Ollama backend: null message content is rejected there (not by vLLM)
    import ollama_compat
    ollama_compat.install()
alias = validate_single_declared_model(sub)
(out / "models.yaml").write_text(yaml.safe_dump(
    {"models": {alias: {"path": f"openai/{a.served}", "api_base": a.api_base, "api_key": "EMPTY"}}}))
models = setup_gemma_model_registry(models_yaml_path=str(out / "models.yaml"))
limits, gen = build_submission_limits()
image = "met-sandbox-" + a.repo.split("/")[1].lower() + ":warm"
config = EvalConfig(
    tasks_path=Path(a.tasks_file), snapshots_dir=SNAP, results_dir=out / "harness", submission_dir=sub,
    models=models, sandbox="docker", image=image, wheels_dir=EMPTY_WHEELS,
    timeout_seconds=240, max_time_minutes=a.minutes, max_tool_calls=a.calls, max_turns=80,
    limits=limits, generation_constraints=gen,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
                                                    token_threshold=14336, event_retention_size=5),
    graph_dir="/opt/offline/no_graphs", embeddings_dir="/opt/offline/no_graphs",
    verbose=False, display_mode="quiet",
)

tasks = [t for t in load_tasks(Path(a.tasks_file)) if t.repo == a.repo]
if a.ids:
    tasks = [t for t in tasks if t.instance_id in a.ids.split(",")]
if a.limit:
    tasks = tasks[: a.limit]
res = out / "results.jsonl"
done = {json.loads(l)["id"] for l in res.read_text().splitlines()} if res.exists() else set()
ev = Evaluator(config)
print(f"[{a.condition}] {a.repo}: {len(tasks)} tasks, image {image}, KP={os.environ.get('OFFLINE_KP')} "
      f"GATE={os.environ.get('OFFLINE_GATE')}", flush=True)
for i, t in enumerate(tasks, 1):
    if t.instance_id in done:
        continue
    t0 = time.time()
    try:
        r = asyncio.run(ev.evaluate_task(task=t, task_index=i, total_tasks=len(tasks)))
        rec = {"id": t.instance_id, "repo": t.repo, "resolved": bool(r.resolved), "tool_calls": r.tool_calls,
               "exit": r.test_exit_code, "patch": r.agent_patch or "", "error": r.error, "sec": round(time.time() - t0)}
    except Exception as e:
        rec = {"id": t.instance_id, "repo": t.repo, "resolved": False, "patch": "", "error": repr(e)[:500],
               "sec": round(time.time() - t0)}
    with res.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[{i}/{len(tasks)}] {t.instance_id} resolved={rec['resolved']} calls={rec.get('tool_calls')} "
          f"patch={len(rec['patch'])} sec={rec['sec']} err={(rec['error'] or '')[:60]}", flush=True)
