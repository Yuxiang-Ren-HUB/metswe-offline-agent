"""List merged PRs with linked issues (since a date) via GitHub search, then intersect with git candidates.

Writes linked_prs.json (PR number, title, body, merged date per repo) and prints the intersection with
cand_<repo>.json (PRs touching >=1 test file and 1-3 non-test source files).
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(sys.argv[1])
SINCE = sys.argv[2] if len(sys.argv) > 2 else "2023-01-01"
REPOS = ["Unidata/MetPy", "pySTEPS/pysteps", "ARM-DOE/pyart", "pytroll/satpy", "wradlib/wradlib",
         "pydata/xarray", "NCAR/geocat-comp", "pytroll/pyresample", "ecmwf/cfgrib"]
CLOSE_RE = re.compile(r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b[\s:]*(?:([\w.-]+/[\w.-]+))?#(\d+)")


def search(q, page):
    url = f"https://api.github.com/search/issues?per_page=100&page={page}&q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "mine"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


out = {}
for repo in REPOS:
    items, page = [], 1
    while True:
        for attempt in range(3):
            try:
                d = search(f"repo:{repo} is:pr is:merged linked:issue merged:>={SINCE}", page)
                break
            except Exception as e:
                print("retry", repo, page, e, flush=True)
                time.sleep(65)
        time.sleep(7)
        for it in d["items"]:
            body = it.get("body") or ""
            refs = [int(n) for own, n in CLOSE_RE.findall(body) if not own or own.lower() == repo.lower()]
            items.append({"pr": it["number"], "title": it["title"], "merged": (it.get("pull_request") or {}).get("merged_at"),
                          "closes_in_body": sorted(set(refs)), "body": body})
        if len(d["items"]) < 100 or page * 100 >= min(d["total_count"], 1000):
            break
        page += 1
    out[repo] = items
    print(repo, len(items), flush=True)

(HERE / "linked_prs.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

print("\nrepo            linked  ∩cand(test,≤3src)  of which body names issue")
tot = [0, 0, 0]
for repo, items in out.items():
    name = repo.split("/")[1]
    cand = {c["pr"] for c in json.loads((HERE / f"cand_{name}.json").read_text(encoding="utf-8"))}
    inter = [i for i in items if i["pr"] in cand]
    named = [i for i in inter if i["closes_in_body"]]
    tot = [tot[0] + len(items), tot[1] + len(inter), tot[2] + len(named)]
    print(f"{name:14s} {len(items):7d} {len(inter):18d} {len(named):26d}")
print(f"{'TOTAL':14s} {tot[0]:7d} {tot[1]:18d} {tot[2]:26d}")
