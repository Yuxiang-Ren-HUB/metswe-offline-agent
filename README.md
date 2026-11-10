# MetSWE offline agent

Code, data and per-task results for the paper *MetSWE: An Offline Benchmark for Gemma 4 Coding Agents on Weather Software* (Gemma 4 Developer Agent competition, paper track).

MetSWE is a set of 147 execution-validated repair tasks from eight Python libraries used in atmospheric science (MetPy, Py-ART, pysteps, wradlib, Satpy, pyresample, geocat-comp, xarray). Each task comes with an offline sandbox recipe in which the official grader runs with networking disabled. The paper uses it to measure a local Gemma 4 31B agent on one RTX 4090 and two in-sandbox additions: an offline API knowledge pack and mechanical pre-submission gates.

This page has five parts:
1. a quick check that a task behaves as validated;
2. the task list and splits;
3. recomputing the paper's tables and figures (CPU only, no Docker);
4. building the environments and running offline;
5. known limitations.

Section 3 needs nothing but Python. Sections 1 and 4 need Docker and the competition's harness.

## 1. Quick check: the empty patch fails, the gold patch passes

Prerequisites, prepared once **with** network access (Section 4 has the details):
- WSL2 or Linux with Docker;
- Python 3.12 with the competition's `swegemma` 0.2.7 harness installed from its wheelhouse;
- the Py-ART image `met-sandbox-pyart:warm` (`bash env/build_image.sh pyart`);
- the two task snapshots (`python benchmark/validate_tasks.py snapshot --ids pyart__1894,pyart__1895`).

Then, **without** network access:

```bash
python benchmark/verify_demo.py --ids pyart__1894,pyart__1895 --out /tmp/metswe_demo.jsonl
```

Expected output: for each task, `empty patch resolved=False`, `gold patch resolved=True`, then `2 / 2 tasks behave as validated`. The grader starts its containers with `network_mode=none`. The script makes no network calls, and talks to Docker over its local socket. To check that it does not depend on the host network, you can run it inside a network namespace without network: `sudo unshare -n -- <python> benchmark/verify_demo.py ...`. Any task id from `benchmark/tasks_final.jsonl` works, once its repository image and snapshot exist.

## 2. Tasks and splits

| File | Contents |
|---|---|
| `benchmark/tasks_final.jsonl` | The 147 tasks: issue text, base commit, gold patch, test patch, merge date, source PR and issue, overlap with other benchmarks |
| `benchmark/tasks_exp100.jsonl` | MetSWE-100, the experiment subset: all 71 non-xarray tasks and 29 xarray tasks drawn with a fixed seed |
| `benchmark/validation_rounds.jsonl`, `benchmark/validation.jsonl` | Grader runs behind every kept or dropped candidate (279 executed); the final re-check on the final images |
| `benchmark/funnel.py` | Recomputes the selection funnel (3,467 → 408 → 279 → 154 → 147) and the reasons for dropping candidates |
| `benchmark/task_types_reviewed.jsonl` | One problem type per MetSWE-100 task and a domain-specific flag. Labels were assigned by an LLM and reviewed in a second LLM pass; no human validation |
| `benchmark/overlap_check.md` | Which other SWE-style task sets contain these repositories, and the limits of that check |

**Development and held-out tasks.** Experiments ran in rounds over the first *k* tasks of each repository in `tasks_exp100.jsonl`. The 47 tasks gate v1 ran on (the first 10 or fewer per repository) are the development set; the other 53 (34 Satpy, 19 xarray) are held out. `results/31b_gate/results.jsonl` lists the development task ids.

## 3. Recomputing the paper's numbers (CPU only)

```bash
python3 analysis/final_summary.py     # outcome tables, sign tests, per-repository counts
python3 analysis/replication.py       # run 2 against run 1, rerun agreement, losses; Figure 3 data
python3 analysis/cpu_extra.py         # random-thinning baseline, bootstrap intervals, post-hoc filter
python3 analysis/gate_evidence.py     # what the gates rejected and repaired
python3 analysis/call_budget.py       # where gate v2's tool calls go, from the agent traces
python3 analysis/verify_claims.py     # spot checks of individual claims
python3 analysis/hard_evidence.py     # what each G4 rejection rested on
python3 analysis/domain_sensitivity.py  # domain-specific vs generic tasks (exploratory)
python3 analysis/ablation.py          # ablations A and B: Table 2 and the mechanism metrics
python3 analysis/ablation_thinning.py # random-thinning check for every condition; Figure 2 data
python3 analysis/abl_extra.py         # why tasks end with no patch (exploratory)
python3 figures/plot_figs_atm.py      # Figures 1-3 of the paper, written to figures/atm/
```

`analysis/ablation_analysis_plan.md` is the analysis plan for the ablations, frozen before any ablation result was inspected, with the execution record and the analyses added afterwards. Held-out ablation rows disrupted by another GPU job and discarded under its timing rule are kept unchanged in `results/_discarded_20261108/`.

Every script reads only `results/` and `benchmark/`.
- `results/31b_<condition>/results.jsonl` has one line per task: resolved, patch, tool calls, error, time.
- `offline_events.jsonl` logs the gate and knowledge-pack calls.
- `harness/traces/` holds the full agent trajectories.

The plotting scripts need matplotlib and numpy; the analysis scripts need only the standard library.

**Main results on MetSWE-100** (one row per run; 100 tasks each):

| Run | Resolved | Failing patch | No patch | Coverage | Precision |
|---|---|---|---|---|---|
| base, run 1 | 19 | 65 | 16 | 0.84 | 0.23 |
| base, run 2 | 22 | 65 | 13 | 0.87 | 0.25 |
| gate v2, run 1 | 20 | 43 | 37 | 0.63 | 0.32 |
| gate v2, run 2 | 17 | 46 | 37 | 0.63 | 0.27 |
| ablation A (prompt only) | 21 | 53 | 26 | 0.74 | 0.28 |
| ablation B (shell fix) | 19 | 30 | 51 | 0.49 | 0.39 |
| knowledge pack | 18 | 68 | 14 | 0.86 | 0.21 |

Gate v1 and knowledge pack + gate v1 ran only on the 47 development tasks (`results/31b_gate`, `results/31b_kp_gate`).

## 4. Building the environments and running offline

**Preparation, with network access:**
1. `bash env/setup_wsl.sh`: Docker, the competition harness, and the competition's base image `swebench-sandbox:latest`.
2. `bash env/build_image.sh <repo>` for each repository you need (`metpy`, `geocat-comp`, `pyart`, `pyresample`, `satpy`, `wradlib`, `pysteps`, `xarray`).
   - The script reproduces the layer order of the images used in the paper, as read from their `docker history`.
   - It ends with a warm-up that runs every task's tests once, so that data caches are baked into the `:warm` image.
   - Package versions are resolved at build time. `bash env/build_image.sh --check <repo>` compares the result with `env/locks/<repo>.txt`, the `pip freeze` of the paper's images. `env/locks/image_ids.txt` gives those images' ids.
3. `python benchmark/validate_tasks.py snapshot --ids <ids>`: repository snapshots at each task's base commit, with 30 commits of history.

**Offline:**
- `benchmark/verify_demo.py` checks any task (Section 1).
- `benchmark/validate_tasks.py verify` repeats the full validation.
- Re-running the agent needs Ollama serving the Gemma 4 31B QAT Q4_0 GGUF at 32K context. The experiment queues `agent/run_all.sh`, `run2.sh`, `run3.sh` and `run4.sh` are kept exactly as run.
- Sampling uses temperature 0.2, so a re-run reproduces the distribution of outcomes, not the same trajectories.

**Paths to edit.** The scripts were written for one machine:
- `/opt/offline` for snapshots, logs and outputs (override with `OFFLINE_WORK`);
- `/mnt/f/kaggle/gemma_agent/...` for this tree and the competition data;
- a local proxy at `127.0.0.1:7897` in the older build scripts.

Edit these at the top of each script before running.

## 5. Known limitations

- **Harness.** The harness is the competition's `swegemma` 0.2.7, which is not redistributed here. The competition later moved to 0.2.11; our gold-patch validation and all runs used 0.2.7.
- **Grading.** The grader requires every test in the touched test files to pass. Some candidates were dropped because their gold patch failed its own tests offline, which biases the set towards tasks with self-contained tests.
- **Repositories.** Most meteorology-specific repositories contribute only 2–9 tasks, and the held-out split covers only Satpy and xarray.
- **Overlap check.** It covers eight task sets as served on 2026-10-12; dataset revisions were not recorded (see `benchmark/overlap_check.md`).
- **Task labels.** Labels in `task_types_reviewed.jsonl` were assigned by an LLM and reviewed by an LLM, without human validation.
- **Rebuilt images.** A rebuilt image can differ in package versions from the paper's; check with `build_image.sh --check`.

## License

Apache 2.0, see `LICENSE`. Task data quote issue text and patches from the upstream repositories, which remain under their own licenses.
