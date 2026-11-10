"""Fetch issue texts in bulk through the search API (separate 10 req/min quota, 100 items per page).

The core REST quota (60/h unauthenticated, per IP) is exhausted behind the shared proxy, so instead of
one request per issue we list `is:issue linked:pr` issues per repository and keep the ones referenced
by candidate PRs. Output: issues.jsonl (one record per referenced issue that was found).
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(sys.argv[1])
SINCE = sys.argv[2] if len(sys.argv) > 2 else "2022-06-01"  # issues may predate their fixing PR


def search(q, page):
    url = f"https://api.github.com/search/issues?per_page=100&page={page}&q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "mine"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


L = json.loads((HERE / "linked_prs.json").read_text(encoding="utf-8"))
wanted = {}
for repo, items in L.items():
    name = repo.split("/")[1]
    cand = {c["pr"] for c in json.loads((HERE / f"cand_{name}.json").read_text(encoding="utf-8"))}
    for it in items:
        if it["pr"] in cand:
            for n in it["closes_in_body"]:
                wanted.setdefault(repo, {})[n] = it["pr"]

found = []
for repo, nums in wanted.items():
    got, page = {}, 1
    while True:
        for attempt in range(4):
            try:
                d = search(f"repo:{repo} is:issue linked:pr created:>={SINCE}", page)
                break
            except Exception as e:
                print("retry", repo, page, e, flush=True)
                time.sleep(65)
        else:
            break
        time.sleep(7)
        for it in d["items"]:
            if it["number"] in nums:
                got[it["number"]] = it
        if len(d["items"]) < 100 or page * 100 >= min(d["total_count"], 1000) or len(got) == len(nums):
            break
        page += 1
    for n, it in got.items():
        found.append({"repo": repo, "issue": n, "pr": nums[n], "title": it["title"], "body": it.get("body") or "",
                      "created_at": it["created_at"], "labels": [l["name"] for l in it.get("labels", [])]})
    print(f"{repo}: {len(got)}/{len(nums)} referenced issues found", flush=True)

with (HERE / "issues.jsonl").open("w", encoding="utf-8") as f:
    for rec in found:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("total", len(found), "of", sum(len(v) for v in wanted.values()))
