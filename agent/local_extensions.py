"""Experiment conditions for the local (modified) harness: knowledge pack tool and pre-submission gates.

Import and call `install()` before building the swegemma Evaluator. Conditions come from env vars:
  OFFLINE_KP=1     register `search_api_docs` as a native tool (agent.yaml must list it)
  OFFLINE_GATE=1   gate submit_patch (feedback + retry, abstain after OFFLINE_GATE_MAX failures)
                   and the fallback path (unsubmitted work that fails the gates is discarded)
  OFFLINE_GATE_VERSION=1|2
                   1: any failed gate is a rejection (abstain after OFFLINE_GATE_MAX on submit, at once on fallback)
                   2: repair what is mechanical first (presubmit_check --clean), then abstain only on evidence
                      against the patch: no source change, stray/test files left, compile/import failure, or a
                      reproduction that still fails with the patch. A missing or uninformative reproduction and
                      related-test regressions (often the intended behaviour change) are warnings: reported to
                      the agent once on submit, ignored on the fallback path.
  OFFLINE_LOG=path JSONL log of every gate run and abstention (one record per event)

The scripts that run inside the sandbox are the same files shipped as skills for the leaderboard
version (agent/skills/*/scripts), copied into the container on first use.
"""
import base64
import json
import os
import shlex
import time
from pathlib import Path

from swegemma import context as sg_context
from swegemma.tools.base import budget_gated, error_response, ok_response

HERE = Path(__file__).resolve().parent
SCRIPTS = {
    "search_api_docs.py": HERE / "skills/api-docs/scripts/search_api_docs.py",
    "presubmit_check.py": HERE / "skills/presubmit-check/scripts/presubmit_check.py",
}
REMOTE_DIR = "/tmp/_offline_tools"
GATE_TIMEOUT = int(os.environ.get("OFFLINE_GATE_TIMEOUT", "600"))
GATE_VERSION = int(os.environ.get("OFFLINE_GATE_VERSION", "1"))


def _flag(name):
    return os.environ.get(name, "0") == "1"


def _task_id(ctx):
    return getattr(ctx, "_task_id", None) or getattr(getattr(ctx, "task", None), "instance_id", None)


def _log(event, ctx, **data):
    path = os.environ.get("OFFLINE_LOG")
    if not path:
        return
    rec = {"t": time.time(), "event": event, "task": _task_id(ctx), **data}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _ensure_scripts(ctx):
    if getattr(ctx, "_offline_tools_ready", False):
        return
    for name, src in SCRIPTS.items():
        b64 = base64.b64encode(src.read_bytes()).decode()
        ctx.docker.exec(ctx.container_id, f"mkdir -p {REMOTE_DIR} && echo {b64} | base64 -d > {REMOTE_DIR}/{name}")
    ctx._offline_tools_ready = True


# ------------------------------------------------------------------ knowledge pack tool
@budget_gated
def search_api_docs(ctx, query: str = "", package: str = "", show: str = "") -> str:
    _ensure_scripts(ctx)
    args = []
    if show:
        args += ["--show", show]
    if package:
        for p in package.replace(",", " ").split():
            args += ["--package", p]
    args += query.split() if query else []
    cmd = f"cd /workspace && python3 {REMOTE_DIR}/search_api_docs.py " + " ".join(shlex.quote(a) for a in args)
    res = ctx.docker.exec(ctx.container_id, cmd, timeout=ctx.harness.command_timeout_seconds)
    _log("kp_query", ctx, query=query, package=package, show=show, exit=res.exit_code)
    if res.exit_code != 0:
        return error_response("SearchError", (res.stderr or res.stdout)[-2000:])
    return ok_response(results=res.stdout[: ctx.harness.max_stdout_chars or 20000])


def make_search_api_docs(ctx):
    def search_api_docs_tool(query: str = "", package: str = "", show: str = "") -> str:
        """Search the documentation of the libraries installed in this offline sandbox.

        There is no internet access, so use this instead of looking up docs online. Use it when you
        know what you want to do but not which function does it, before calling a library function
        whose name or arguments you are unsure of, or after an AttributeError / unexpected keyword
        argument / ImportError from a library call.

        Args:
            query: What you want to do, in words or identifiers (e.g. "interpolate onto new coordinates").
            package: Optional top-level package(s) to restrict the search to (e.g. "xarray" or "numpy scipy").
            show: Optional full API name to print its complete docstring (e.g. "numpy.nanmax").
        """
        return search_api_docs(ctx, query=query, package=package, show=show)

    search_api_docs_tool.__name__ = "search_api_docs"
    return search_api_docs_tool


# ------------------------------------------------------------------ gates
def run_gates(ctx):
    _ensure_scripts(ctx)
    t0 = time.time()
    res = ctx.docker.exec(ctx.container_id, f"cd /workspace && python3 {REMOTE_DIR}/presubmit_check.py", timeout=GATE_TIMEOUT)
    try:
        report = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError):
        report = {"all_pass": False, "crash": (res.stdout or "")[-1500:] + (res.stderr or "")[-1500:]}
    report["seconds"] = round(time.time() - t0, 1)
    return report


def clean_workspace(ctx):
    _ensure_scripts(ctx)
    res = ctx.docker.exec(ctx.container_id, f"cd /workspace && python3 {REMOTE_DIR}/presubmit_check.py --clean", timeout=GATE_TIMEOUT)
    try:
        done = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError):
        done = {"crash": (res.stdout or "")[-500:] + (res.stderr or "")[-500:]}
    if done.get("removed") or done.get("restored") or done.get("crash"):
        _log("clean", ctx, **done)
    return done


def hard_failures(report):
    """Gate version 2: the failures that are evidence against the patch itself."""
    hard = [k for k in ("G1_clean_files", "G2_no_test_edits", "G3_compiles") if not report.get(k, {}).get("pass", True)]
    if report.get("G4_repro_flips", {}).get("kind") == "fails_with_patch":
        hard.append("G4_repro_flips")
    return hard


def gate_feedback(report):
    lines = [f"{k}: {v['detail']}" for k, v in report.items() if isinstance(v, dict) and not v.get("pass")]
    if "crash" in report:
        lines.append("gate checker crashed: " + report["crash"][-800:])
    return "Your patch did not pass the pre-submission checks. Fix the problems below and call submit_patch again.\n" + "\n".join(lines)


def warning_feedback(report):
    lines = [f"{k}: {v['detail']}" for k, v in report.items() if isinstance(v, dict) and not v.get("pass")]
    return ("The pre-submission checks raised warnings (not errors). Address them if they reveal a real problem; "
            "if a related test fails only because the issue asks for that behaviour to change, keep your fix. "
            "Call submit_patch again to submit.\n" + "\n".join(lines))


def abstain(ctx, reason):
    ctx.docker.exec(ctx.container_id, "cd /workspace && git reset -q --hard _swegemma_baseline && git clean -q -fd")
    ctx.submitted_patch = ""
    ctx.patch_submitted = True
    ctx.gate_abstained = True
    _log("abstain", ctx, reason=reason)


def make_gated_submit(ctx, original):
    max_fail = int(os.environ.get("OFFLINE_GATE_MAX", "3"))
    if GATE_VERSION == 2:
        return make_gated_submit_v2(ctx, original, max_fail)

    def submit_patch_tool() -> str:
        """Capture the current working tree modifications as the agent's submission.

        Before the patch is accepted it must pass pre-submission checks: a reproduction script at
        /tmp/repro.py that fails on the original code and passes with your change, no edits to test
        or config files, no stray files, the code compiles and imports, and related tests do not
        regress. If a check fails you get the reason and can fix it and submit again.
        """
        report = run_gates(ctx)
        ctx._gate_runs = getattr(ctx, "_gate_runs", 0) + 1
        _log("gate", ctx, path="submit", attempt=ctx._gate_runs, report=report)
        if report.get("all_pass"):
            return original()
        if ctx._gate_runs >= max_fail:
            abstain(ctx, f"failed gates {ctx._gate_runs} times")
            return ok_response(abstained=True, message="The patch failed the pre-submission checks too many times; "
                                                       "it was withdrawn and nothing was submitted.")
        return error_response("PresubmitGateFailed", gate_feedback(report),
                              details={"attempt": ctx._gate_runs, "max_attempts": max_fail})

    submit_patch_tool.__name__ = "submit_patch"
    return submit_patch_tool


def make_gated_submit_v2(ctx, original, max_fail):
    def submit_patch_tool() -> str:
        """Capture the current working tree modifications as the agent's submission.

        Before the patch is accepted it must pass pre-submission checks: a reproduction script at
        /tmp/repro.py that fails on the original code and passes with your change, no edits to test
        or config files, no stray files, the code compiles and imports, and related tests do not
        regress. If a check fails you get the reason and can fix it and submit again.
        """
        clean_workspace(ctx)
        report = run_gates(ctx)
        hard = hard_failures(report)
        ctx._gate_runs = getattr(ctx, "_gate_runs", 0) + 1
        _log("gate", ctx, path="submit", attempt=ctx._gate_runs, version=2, hard=hard, report=report)
        if report.get("all_pass") or "crash" in report:  # a crashed checker is no evidence against the patch
            return original()
        if hard:
            ctx._gate_hard = getattr(ctx, "_gate_hard", 0) + 1
            if ctx._gate_hard >= max_fail:
                abstain(ctx, f"failed hard gates {ctx._gate_hard} times: {hard}")
                return ok_response(abstained=True, message="The patch failed the pre-submission checks too many times; "
                                                           "it was withdrawn and nothing was submitted.")
            return error_response("PresubmitGateFailed", gate_feedback(report),
                                  details={"attempt": ctx._gate_hard, "max_attempts": max_fail})
        if not getattr(ctx, "_gate_warned", False):  # warnings only: tell the agent once, then accept
            ctx._gate_warned = True
            return error_response("PresubmitWarning", warning_feedback(report))
        return original()

    submit_patch_tool.__name__ = "submit_patch"
    return submit_patch_tool


# ------------------------------------------------------------------ install
def install():
    kp, gate = _flag("OFFLINE_KP"), _flag("OFFLINE_GATE")
    Ctx = sg_context.SwegemmaContext
    if getattr(Ctx, "_offline_installed", False):
        return
    orig_create, orig_stop = Ctx.create_tools, Ctx.stop_agent_session

    def create_tools(self):
        tools = orig_create(self)
        if kp:
            tools["search_api_docs"] = make_search_api_docs(self)
        if gate:
            tools["submit_patch"] = make_gated_submit(self, tools["submit_patch"])
        return tools

    def stop_agent_session(self):
        orig_stop(self)
        # the harness turns unsubmitted working-tree changes into the patch right after this call,
        # so unsubmitted work has to pass the same gates or be discarded (abstention)
        if gate and GATE_VERSION == 2 and not self.patch_submitted and self.container_id:
            try:
                clean_workspace(self)
                st = self.docker.exec(self.container_id, "cd /workspace && git status --porcelain")
                if st.stdout.strip():
                    report = run_gates(self)
                    hard = hard_failures(report)
                    _log("gate", self, path="fallback", version=2, hard=hard, report=report)
                    if hard and "crash" not in report:
                        abstain(self, f"unsubmitted changes failed hard gates: {hard}")
            except Exception as e:
                _log("hook_error", self, error=repr(e))
        elif gate and not self.patch_submitted and self.container_id:
            try:
                # mechanical cleanup first: untracked scratch scripts at the repository root (repro.py, test_x.py,
                # debug.py ...) are never part of a fix, and the agent can no longer act on gate feedback here
                # (no '*.py' filter: the model sometimes writes names like "repro.py`")
                self.docker.exec(self.container_id, "cd /workspace && git ls-files --others --exclude-standard "
                                 "| grep -v / | grep -E '^(repro|reproduce|debug|scratch|test_|tmp)' | xargs -r -d '\\n' rm -f")
                st = self.docker.exec(self.container_id, "cd /workspace && git status --porcelain")
                if st.stdout.strip():
                    report = run_gates(self)
                    _log("gate", self, path="fallback", report=report)
                    if not report.get("all_pass"):
                        abstain(self, "unsubmitted changes failed the gates")
            except Exception as e:  # never let the experiment hook crash the harness
                _log("hook_error", self, error=repr(e))

    Ctx.create_tools = create_tools
    Ctx.stop_agent_session = stop_agent_session
    Ctx._offline_installed = True
    print(f"[offline] knowledge pack={'on' if kp else 'off'}  gates={'v%d' % GATE_VERSION if gate else 'off'}")
