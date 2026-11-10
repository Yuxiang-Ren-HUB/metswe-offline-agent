"""Turn candidate PRs into SWE-bench-style task records (not yet execution-validated).

For each candidate PR commit on the default branch: base_commit = first parent; patch = diff of
non-test files; test_patch = diff of test files (the grader's protected-path rule decides which is
which); problem_statement = linked issue title + body. Writes tasks_unvalidated.jsonl.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(sys.argv[1])
REPOS = Path(sys.argv[2])
CUTOFF = "2025-02-01"
PROTECTED = {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini"}


def is_test(path):  # same rule as the grader (swegemma.harness.verification._is_protected_test_or_config_path)
    p = Path(path)
    name = p.name
    if name in PROTECTED or name.endswith(".pth"):
        return True
    if name.startswith("test_") and name.endswith(".py") or name.endswith("_test.py"):
        return True
    return bool({"tests", "test", "testing"} & {x.lower() for x in p.parts[:-1]} and name.endswith(".py"))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


issues = {}
for line in (HERE / "issues.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    issues[(d["repo"], d["issue"])] = d

linked = json.loads((HERE / "linked_prs.json").read_text(encoding="utf-8"))
out, skipped = [], {"no_issue_text": 0, "no_src_diff": 0, "binary_or_data": 0}
for repo, items in linked.items():
    name = repo.split("/")[1]
    clone = REPOS / name
    cand = {c["pr"]: c for c in json.loads((HERE / f"cand_{name}.json").read_text(encoding="utf-8"))}
    for it in items:
        c = cand.get(it["pr"])
        if not c:
            continue
        texts = [issues[(repo, n)] for n in it["closes_in_body"] if (repo, n) in issues]
        if not texts:
            skipped["no_issue_text"] += 1
            continue
        commit = c["hash"]
        base = git(clone, "rev-parse", f"{commit}^1").strip()
        files = [f for f in git(clone, "diff", "--name-only", base, commit).splitlines() if f]
        test_files = [f for f in files if is_test(f)]
        src_files = [f for f in files if not is_test(f)]
        if not any(f.endswith(".py") for f in src_files):
            skipped["no_src_diff"] += 1
            continue
        patch = git(clone, "diff", "--binary", base, commit, "--", *src_files)
        test_patch = git(clone, "diff", "--binary", base, commit, "--", *test_files) if test_files else ""
        if "GIT binary patch" in patch + test_patch:
            skipped["binary_or_data"] += 1  # test data blobs cannot be applied as text patches reliably
            continue
        statement = "\n\n".join(f"{t['title']}\n\n{t['body']}".strip() for t in texts)
        merged = it["merged"] or c["date"]
        out.append({
            "instance_id": f"{name.lower()}__{it['pr']}",
            "repo": repo, "pr": it["pr"], "issues": [t["issue"] for t in texts],
            "base_commit": base, "merge_commit": commit, "merged_at": merged,
            "post_cutoff": merged >= CUTOFF,
            "problem_statement": statement, "patch": patch, "test_patch": test_patch,
            "src_files": src_files, "test_files": test_files,
            "lines_changed": sum(1 for l in patch.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))),
            "hints": {
                "uses_pooch_or_network": bool(re.search(r"pooch|requests\.get|urlopen|@pytest\.mark\.network|get_test_data", test_patch)),
                "mpl_image_test": "mpl_image_compare" in test_patch,
                "touches_extension": any(f.endswith((".pyx", ".c", ".cpp", ".f90")) for f in src_files),
            },
        })
    print(name, sum(1 for o in out if o["repo"] == repo), flush=True)

with (HERE / "tasks_unvalidated.jsonl").open("w", encoding="utf-8") as f:
    for o in out:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
post = [o for o in out if o["post_cutoff"]]
print("tasks", len(out), "post-cutoff", len(post), "non-xarray post-cutoff", sum(o["repo"] != "pydata/xarray" for o in post))
print("skipped", skipped)
print("hints (post-cutoff):", {k: sum(o["hints"][k] for o in post) for k in post[0]["hints"]} if post else {})
