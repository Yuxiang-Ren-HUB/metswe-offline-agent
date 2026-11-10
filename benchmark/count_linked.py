"""Count merged PRs with linked issues per repo via GitHub search (unauthenticated, 10 req/min)."""
import json
import sys
import time
import urllib.request

OUT = sys.argv[1]
REPOS = ["Unidata/MetPy", "pySTEPS/pysteps", "ARM-DOE/pyart", "pytroll/satpy", "wradlib/wradlib",
         "pydata/xarray", "NCAR/geocat-comp", "pytroll/pyresample", "ecmwf/cfgrib"]
QUERIES = {
    "merged": "is:pr is:merged",
    "linked": "is:pr is:merged linked:issue",
    "linked_since_2024": "is:pr is:merged linked:issue merged:>=2024-01-01",
    "linked_since_2025": "is:pr is:merged linked:issue merged:>=2025-01-01",
}


def count(q):
    url = "https://api.github.com/search/issues?per_page=1&q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "count-script"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["total_count"]


res = {}
for repo in REPOS:
    res[repo] = {}
    for k, q in QUERIES.items():
        for attempt in range(3):
            try:
                res[repo][k] = count(f"repo:{repo} {q}")
                break
            except Exception as e:  # rate limit or transient network error
                print("retry", repo, k, e, flush=True)
                time.sleep(65)
        time.sleep(7)  # stay under 10 search requests per minute
    print(repo, res[repo], flush=True)

json.dump(res, open(OUT, "w"), indent=1)
tot = {k: sum(v.get(k, 0) for v in res.values()) for k in QUERIES}
print("TOTAL", tot)
