"""Count SWE-bench-style candidate PRs in local (partial) clones, using git history only.

A candidate is a first-parent commit on the default branch that comes from a PR
(merge commit or squash "(#N)") and changes >=1 test file and >=1 non-test source .py file.
Issue links are only partly visible in commit messages, so the "issue-ref" column is a lower bound.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPOS = Path(sys.argv[1])
OUT = Path(sys.argv[2])

PR_RE = re.compile(r"Merge pull request #(\d+)|\(#(\d+)\)\s*$")
ISSUE_RE = re.compile(r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b[\s:]*(?:[\w.-]+/[\w.-]+)?#(\d+)")
NON_SRC = re.compile(r"(^|/)(docs?|examples?|ci|benchmarks?|asv_bench|tutorials?|\.github)/")


def is_test(p):
    name = p.rsplit("/", 1)[-1]
    return "/tests/" in "/" + p or "/testing/" in "/" + p or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def mine(repo):
    # bodies (for issue refs), keyed by hash
    raw = git(repo, "log", "--first-parent", "--format=%H%x1f%B%x1e", "HEAD")
    bodies = {}
    for rec in raw.split("\x1e"):
        if "\x1f" in rec:
            # str.strip() treats \x1f as whitespace, so strip newlines only
            h, b = rec.strip("\n").split("\x1f", 1)
            bodies[h] = b
    # changed files per first-parent commit (merges diffed against first parent)
    raw = git(repo, "log", "--first-parent", "--diff-merges=first-parent", "--name-only",
              "--format=\x1e%H\x1f%ad\x1f%s", "--date=short", "HEAD")
    rows = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        head, *files = rec.split("\n")
        h, date, subj = head.split("\x1f", 2)
        m = PR_RE.search(subj)
        if not m:
            continue
        files = [f for f in files if f.strip()]
        tests = [f for f in files if f.endswith(".py") and is_test(f)]
        src = [f for f in files if f.endswith(".py") and not is_test(f) and not NON_SRC.search(f)]
        body = bodies.get(h, "")
        issues = sorted({int(x) for x in ISSUE_RE.findall(subj + "\n" + body)})
        rows.append({"hash": h, "date": date, "pr": int(m.group(1) or m.group(2)), "subject": subj,
                     "n_test": len(tests), "n_src": len(src), "issues": issues})
    return rows


summary = {}
for repo in sorted(p for p in REPOS.iterdir() if (p / ".git").exists()):
    rows = mine(repo)
    cand = [r for r in rows if r["n_test"] >= 1 and r["n_src"] >= 1]
    small = [r for r in cand if r["n_src"] <= 3]
    linked = [r for r in small if r["issues"]]
    years = Counter(r["date"][:4] for r in small)
    summary[repo.name] = {
        "pr_commits": len(rows), "test+src": len(cand), "test+src_le3src": len(small),
        "le3src_with_issue_ref_in_msg": len(linked),
        "le3src_since_2024": sum(r["date"] >= "2024-01-01" for r in small),
        "le3src_since_2025": sum(r["date"] >= "2025-01-01" for r in small),
        "le3src_since_2025H2": sum(r["date"] >= "2025-07-01" for r in small),
        "by_year": dict(sorted(years.items())),
    }
    (OUT / f"cand_{repo.name}.json").write_text(json.dumps(small, indent=1), encoding="utf-8")

(OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
cols = ["pr_commits", "test+src", "test+src_le3src", "le3src_with_issue_ref_in_msg",
        "le3src_since_2024", "le3src_since_2025", "le3src_since_2025H2"]
print("repo".ljust(13) + "".join(c[:22].rjust(24) for c in cols))
for k, v in summary.items():
    print(k.ljust(13) + "".join(str(v[c]).rjust(24) for c in cols))
print("TOTAL".ljust(13) + "".join(str(sum(v[c] for v in summary.values())).rjust(24) for c in cols))
