# Which SWE-style task sets contain MetSWE's repositories

Checked on 2026-10-12 against the Hugging Face releases of each task set (task counts by repository). This is the
basis for the statement in the paper that pysteps, Py-ART and wradlib appear in none of the task sets we checked. Task
sets not listed here were not checked.

Limits of this check:
- Dataset revisions (commit hashes) were not recorded at the time; the counts refer to the versions served on 2026-10-12.
- Tasks were counted by the repository named in each record; the counting script was not kept. A re-check should match
  the `repo` field exactly (e.g. `pySTEPS/pysteps`, `ARM-DOE/pyart`, `wradlib/wradlib`) and record the revision used.
- The eight sets are not independent: SWE-bench Verified is a subset of SWE-bench, and SWE-rebench V2 comes from the
  same collection pipeline as SWE-rebench. Other overlaps between sets were not examined.

| Task set (size checked) | MetSWE repositories found | Other geoscience or neighbouring repositories |
|---|---|---|
| SWE-bench, test (2,294) | xarray 110 | astropy 95 |
| SWE-bench Verified (500) | xarray 22 | astropy 22 |
| SWE-rebench, test (21,336) | MetPy 36, xarray 275, geocat-comp 5 | xclim 47, rioxarray 42, regionmask 24, uxarray 21, xradar 13, xESMF 13, siphon 4, others |
| SWE-rebench V2 (32,079) | geocat-comp 3 | earthkit-data 25, pvlib 26, cartopy 4, ACT 3, iris 3 |
| SWE-bench-Live, full (1,888) | MetPy 2, xarray 29 | pvlib 30, cartopy 1 |
| SWE-bench Science (119) | MetPy 1, Satpy 1 | iris, xclim, CLIMADA, xgcm, Parcels, others (one each) |
| SWE-Gym (2,438) | none | none |
| SWE-smith (59,136) | none | sunpy, dask |

- pysteps, Py-ART and wradlib: no tasks in any set above. Satpy: one task (SWE-bench Science). pyresample was not tallied in this check.
- Task-level overlap with MetSWE: two MetPy tasks share a PR number with SWE-rebench; both predate Gemma 4's training cutoff. They are marked in `benchmark/tasks_final.jsonl` (field `overlap`).
