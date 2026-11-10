"""Mechanical pre-submission gates for a patch in /workspace.

Run before submit_patch. Prints a JSON report and exits 0 only if every gate passes:

  G1 clean_files     at least one non-test source file changed (.py, or package data such as reader .yaml); no junk (*.orig/*.rej/*.bak, notebooks, binaries,
                     new repro*/test_* scripts at the repository root)
  G2 no_test_edits   no test/conftest/runner-config file touched (same rule the grader uses; such
                     files are reset before grading, so edits there are lost anyway)
  G3 compiles        every changed .py compiles and every changed module imports
  G4 repro_flips     /tmp/repro.py fails (non-zero exit) on the baseline and passes (exit 0) on the patch
  G5 no_regression   tests related to the changed modules do not gain failures relative to baseline

The baseline is a throw-away copy of the workspace reset to the baseline tag, so /workspace itself
is never modified. With --clean it instead repairs what is mechanical (untracked root scratch scripts are
deleted, test/config files restored) and prints what it changed. Standard library only. Paths can be overridden for local testing:
  PRESUBMIT_WORKSPACE, PRESUBMIT_TMP, PRESUBMIT_BASE_REF, PRESUBMIT_REPRO
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

WS = Path(os.environ.get("PRESUBMIT_WORKSPACE", "/workspace"))
TMP = Path(os.environ.get("PRESUBMIT_TMP", "/tmp"))
BASE_REF = os.environ.get("PRESUBMIT_BASE_REF", "_swegemma_baseline")
REPRO = Path(os.environ.get("PRESUBMIT_REPRO", str(TMP / "repro.py")))
CMD_TIMEOUT = int(os.environ.get("PRESUBMIT_TIMEOUT", "240"))
MAX_TEST_FILES = 3

PROTECTED_NAMES = {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini",
                   "sitecustomize.py", "usercustomize.py", "_swegemma_stubs.py"}
JUNK = re.compile(r"\.(orig|rej|bak|ipynb|pyc|so|dll|exe|png|jpg|nc|h5|grib2?)$", re.I)


def is_protected(rel):  # mirrors swegemma.harness.verification._is_protected_test_or_config_path
    p = Path(rel)
    name = p.name
    if name in PROTECTED_NAMES or name.endswith(".pth"):
        return True
    if name.startswith("test_") and name.endswith(".py") or name.endswith("_test.py"):
        return True
    return bool({"tests", "test", "testing"} & {x.lower() for x in p.parts[:-1]} and name.endswith(".py"))


def run(cmd, cwd, env=None, timeout=CMD_TIMEOUT):
    try:
        r = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        return 124, f"timed out after {timeout}s\n{(e.stdout or '')[-2000:]}"


def tail(text, n=1200):
    text = text.strip()
    return text if len(text) <= n else "..." + text[-n:]


def git(*args):
    return run(["git", *args], WS)


def base_ref():
    code, _ = git("rev-parse", "--verify", "--quiet", BASE_REF)
    return BASE_REF if code == 0 else "HEAD"


def changed_files(ref):
    _, tracked = git("diff", "--name-only", ref)
    _, untracked = git("ls-files", "--others", "--exclude-standard")
    files = {f.strip() for f in (tracked + "\n" + untracked).splitlines() if f.strip()}
    return sorted(f for f in files if not f.startswith(".adk_exec_"))


def py_env(root):
    """Environment whose imports resolve to the given tree (workspace or baseline copy)."""
    paths = [str(root)] + [str(root / "src")] * (root / "src").is_dir()
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(paths + [env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def module_of(rel):
    parts = list(Path(rel).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def make_baseline_copy(ref):
    dest = Path(tempfile.mkdtemp(prefix="presubmit_base_", dir=TMP))
    shutil.copytree(WS, dest / "ws", symlinks=True, dirs_exist_ok=True)
    base = dest / "ws"
    # reset tracked files to the baseline; drop untracked non-ignored files (the agent's new files)
    # while keeping ignored build artefacts such as compiled extensions
    run(["git", "reset", "-q", "--hard", ref], base)
    run(["git", "clean", "-q", "-fd"], base)
    return dest, base


def remove_tree(path):
    def make_writable(func, p, _exc):  # git object files are read-only; needed on Windows
        os.chmod(p, 0o700)
        func(p)
    try:
        shutil.rmtree(path, onerror=make_writable)
    except OSError:
        pass


def is_scratch(rel):  # a root-level scratch script, or anything under a root-level scratch directory
    return bool(re.match(r"(repro|reproduce|debug|scratch|test_|tmp)", rel.split("/")[0]))


def gate_files(files):
    junk = [f for f in files if JUNK.search(f) or (is_scratch(f) and f.endswith(".py"))]
    # a fix can live entirely in package data (e.g. a satpy reader .yaml), so any non-test, non-junk file counts
    src = [f for f in files if not is_protected(f) and f not in junk and not is_scratch(f)]
    ok = bool(src) and not junk
    msg = []
    if not src:
        msg.append("no non-test source file is changed")
    if junk:
        msg.append("remove these files from the patch: " + ", ".join(junk) + " (keep scratch scripts in /tmp)")
    return ok, "; ".join(msg) or f"{len(src)} source file(s) changed"


def gate_tests(files):
    bad = [f for f in files if is_protected(f)]
    return not bad, ("revert edits to test/config files (they are reset before grading): " + ", ".join(bad)) if bad else "ok"


def gate_compiles(files):
    errors = []
    py = [f for f in files if f.endswith(".py") and not is_protected(f) and (WS / f).exists()]
    # import only package modules: a root-level script (e.g. a stray repro.py) would be executed by importing it
    importable = [f for f in py if "/" in f]
    for f in py:
        try:
            ast.parse((WS / f).read_text(encoding="utf-8", errors="replace"), filename=f)
        except SyntaxError as e:
            errors.append(f"{f}:{e.lineno}: SyntaxError: {e.msg}")
    if not errors:
        mods = sorted({module_of(f) for f in importable if module_of(f)})
        if mods:
            code_ = "import importlib, sys\nfor m in sys.argv[1:]:\n    importlib.import_module(m)\n"
            code, out = run([sys.executable, "-c", code_, *mods], WS, env=py_env(WS))
            if code != 0:
                errors.append("import failed:\n" + tail(out, 800))
    return not errors, "\n".join(errors) or "ok"


def gate_repro(base):
    # the third value says what kind of evidence the result is: only "fails_with_patch" is evidence against the
    # patch; "missing" and "passes_on_baseline" say the reproduction is absent or uninformative
    if not REPRO.exists():
        return False, (f"write a reproduction script at {REPRO} that exits non-zero while the bug is present "
                       "(e.g. assert the correct behaviour) and exits 0 once it is fixed"), "missing"
    code_new, out_new = run([sys.executable, str(REPRO)], WS, env=py_env(WS))
    code_old, out_old = run([sys.executable, str(REPRO)], base, env=py_env(base))
    if code_new == 0 and code_old != 0:
        return True, "fails on baseline, passes with the patch", "ok"
    if code_new != 0:
        return False, f"repro still fails with your patch (exit {code_new}):\n{tail(out_new)}", "fails_with_patch"
    return False, ("repro also passes on the unpatched baseline, so it does not reproduce the issue; "
                   f"make it assert the behaviour described in the issue. Baseline output:\n{tail(out_old, 600)}"), "passes_on_baseline"


def related_tests(files, root):
    names = {Path(f).stem for f in files if f.endswith(".py") and not is_protected(f)} - {"__init__"}
    cands = []
    for t in sorted(root.rglob("test_*.py")):
        rel = t.relative_to(root).as_posix()
        if ".git/" in rel:
            continue
        stem = t.stem[len("test_"):]
        score = 2 if stem in names else 0
        if not score:
            try:
                text = t.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            score = 1 if any(re.search(rf"\b{re.escape(n)}\b", text) for n in names) else 0
        if score:
            cands.append((-score, rel))
    return [rel for _, rel in sorted(cands)[:MAX_TEST_FILES]]


def failing_tests(root, tests):
    fd, name = tempfile.mkstemp(suffix=".xml", dir=TMP)
    os.close(fd)  # pytest writes the file itself; an open handle would also block unlink on Windows
    xml = Path(name)
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", *tests],
                    root, env=py_env(root))
    failed = set()
    try:
        for case in ET.parse(xml).getroot().iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                failed.add(f"{case.get('classname')}::{case.get('name')}")
    except (ET.ParseError, FileNotFoundError):
        if code not in (0, 1, 5):
            failed.add(f"<pytest exit {code}>")
    xml.unlink(missing_ok=True)
    return failed, out


def gate_regression(files, base):
    tests = related_tests(files, WS)
    if not tests:
        return True, "no related test files found (nothing to compare)"
    tests_in_base = [t for t in tests if (base / t).exists()]
    new_fail, out = failing_tests(WS, tests)
    old_fail, _ = failing_tests(base, tests_in_base) if tests_in_base else (set(), "")
    regressed = sorted(new_fail - old_fail)
    if regressed:
        return False, f"tests that pass on baseline now fail ({', '.join(tests)}):\n" + "\n".join(regressed[:15]) + "\n" + tail(out, 800)
    return True, f"{len(tests)} related test file(s): no new failures ({len(new_fail)} pre-existing)"


def clean(ref):
    """Mechanical repairs that need no judgement: delete untracked scratch scripts at the repository root and
    untracked data/binary files anywhere (downloaded sample files, plots), and restore test/config files to the baseline (the grader resets them anyway, and an edited test file can make
    the grader's test patch fail to apply)."""
    files = changed_files(ref)
    _, untracked = git("ls-files", "--others", "--exclude-standard")
    untracked = {f.strip() for f in untracked.splitlines() if f.strip()}
    removed, restored = [], []
    for f in files:
        if f in untracked and (is_scratch(f) or is_protected(f) or JUNK.search(f)):
            (WS / f).unlink(missing_ok=True)
            removed.append(f)
        elif is_protected(f):
            git("checkout", ref, "--", f)
            restored.append(f)
    print(json.dumps({"removed": removed, "restored": restored}))


def main():
    ref = base_ref()
    if "--clean" in sys.argv[1:]:
        clean(ref)
        return
    files = changed_files(ref)
    report, ok_all = {"changed_files": files}, True
    for name, fn in (("G1_clean_files", gate_files), ("G2_no_test_edits", gate_tests), ("G3_compiles", gate_compiles)):
        ok, msg = fn(files)
        report[name] = {"pass": ok, "detail": msg}
        ok_all &= ok
    if ok_all:  # execution gates only make sense once the static ones pass
        tmpdir, base = make_baseline_copy(ref)
        try:
            ok, msg, kind = gate_repro(base)
            report["G4_repro_flips"] = {"pass": ok, "detail": msg, "kind": kind}
            ok_all &= ok
            # v1 stopped at the first failing execution gate; G5 now always runs so a soft-gate policy can see it
            ok, msg = gate_regression(files, base)
            report["G5_no_regression"] = {"pass": ok, "detail": msg}
            ok_all &= ok
        finally:
            remove_tree(tmpdir)
    report["all_pass"] = ok_all
    print(json.dumps(report, indent=1))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
