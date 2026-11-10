# Ablation analysis plan (fixed 2026-11-07, before any ablation result was inspected)

Runs (agent/run4.sh, one run each on MetSWE-100, 28 calls, 14 min, same code and sampling as all other runs):
- **A `gateprompt`**: gate v2's prompt (conditions/gate) with the mechanical gate off. No repair, no checks, no rejection.
- **B `gate2sh`**: gate v2 with one prompt sentence added (conditions/gate_sh): create `/tmp/repro.py` with `run_command`.

Script: `analysis/ablation.py` (written before results; only bug fixes allowed afterwards, recorded below).

## Comparisons and what each answers

| Comparison | Question |
|---|---|
| A vs base (run 1, run 2, pooled) | What does the reproduction prompt alone change? |
| A vs gate v2 (run 1, run 2, pooled) | What does the mechanical gate add on top of the prompt? |
| B vs gate v2 (run 1, run 2, pooled) | Does removing the refused write relieve budget pressure? |

A and B ran once, so each is compared with each of the two runs of base / gate v2 and with their mean; differences within the run-to-run range of Section 4.3 (3 resolved, 3 failing for the same condition) are reported as such.

## Metrics, all reported regardless of direction

For every run: resolved, failing patches, no patch, coverage, precision, mean time per task, call-limit hits.
Paired sign tests over the 100 tasks for failing patches and resolutions (A vs base r1/r2, A vs gate v2 r1/r2, B vs gate v2 r1/r2).
Held-out 53 tasks: failing and resolved for A and B.
For B additionally (mechanism): refused `write_file` calls to /tmp/repro.py per task, calls spent on the reproduction per task,
median position of the first source-edit call, call-limit hits, gate rejections and abstentions.
For A additionally: tasks where the agent wrote /tmp/repro.py at all, and refused writes (the same prompt, so they should match gate v2).

## Reporting rules

- Report A and B as ablations of gate v2. Neither replaces gate v2 as the paper's method, whatever the result.
- No further configurations after seeing these results.
- A single run cannot establish a resolved-task difference smaller than the rerun range; the mechanism metrics of B are the primary evidence for B.

## Interpretation, fixed before results (added 2026-11-07, still before any ablation result was inspected)

Revised 2026-11-07, still before any ablation result was inspected: an absolute difference of 3 tasks or fewer in a total is
described as "totals close" for descriptive reference only; it does not mean statistical equivalence. The direction and
strength of evidence come from per-task paired comparisons (discordant counts, exact sign test) and paired bootstrap 95%
intervals over tasks, reported against each run of the reference condition separately. No 3-task threshold is used for
"better". Reruns of one condition cancel out on many tasks (base 9 against 9, gate v2 13 against 16 failing patches), so
equal totals can hide large task-level changes; A and B ran once, and the text states this uncertainty.
In the table below, "close to" and "clearly better" are read in this sense.

Scope of attribution: A separates the reproduction prompt from the rest of gate v2 taken together. It cannot separate
repair, execution checks, feedback and rejection from each other; the paper will not claim that the ablation identifies
the contribution of each component.

| Result | What the paper will say |
|---|---|
| A close to gate v2 on failing patches, clearly better than base | The reproduction prompt carries much of the reduction; the claim for the gate's own contribution is narrowed accordingly. |
| A close to base, gate v2 clearly better than A | The reduction comes mainly from the gate's repair, checks and rejection, not from the prompt. |
| A between the two | Both contribute; report the split (base → A → gate v2) without ranking them beyond the data. |
| B cuts refused writes and call-limit hits, and resolved or failing improve beyond the rerun range | Supports the budget-competition explanation, with the fix validated in one run. |
| B cuts refused writes and call-limit hits, outcomes change within the rerun range | The waste is real but not the main bottleneck; say so. |
| B does not cut refused writes | The prompt change did not take effect; report as a failed fix, no further variants. |

Whatever the outcome, the abstract and contributions are rewritten to match this table; the earlier wording is not kept by default.

Reporting completeness: every pre-specified comparison is reported, A against both runs of base and both runs of gate v2,
and B against both runs of gate v2, whichever is significant or favourable. These comparisons share tasks and runs and are
not independent replications; the text does not call them that.

**Plan frozen on 2026-11-07, before any ablation result was inspected.** Later entries below are limited to bug fixes in
`analysis/ablation.py`, each recorded with its reason.

## Changes after results
(none yet)

## Execution record (not a change to the analysis)
On 2026-11-08 at 06:27 another GPU job started on the same card while the ablations were running. From then on, model calls
timed out and tasks were recorded with zero tool calls at the 14-minute session limit. The run was stopped at 20:15.
Decision rule, set from timestamps and the zero-call signature, before any resolved count was examined: rounds 3–10 (the 47
development tasks, both conditions, all finished before 06:27) stand; everything from round 15 on (the 53 held-out tasks, both
conditions) is discarded and re-run, regardless of outcome. `run4.sh` is unchanged. The discarded rows, traces and logs are
kept in `_invalid_20261108/`. Valid and re-run rows therefore come from two sessions, and the paper states this.

## Exploratory analyses added after the results (not part of the frozen plan)
`analysis/ablation_thinning.py` extends the paper's random-thinning comparison to A and B (excess resolved over dropping base's patches at random to the same submission count, paired bootstrap over tasks). The no-patch breakdown by end reason is also exploratory. Both are labelled exploratory in the text.
