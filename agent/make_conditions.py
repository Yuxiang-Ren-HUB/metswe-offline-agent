"""Generate the four experiment conditions (base, kp, gate, kp_gate) from the official sample agent.

Shared changes to the official baseline, applied to every condition:
  - graph tools and the code_analyzer sub-agent removed (no precomputed graphs for the new repositories;
    the prompt's search_similar_code hint is replaced by a grep hint);
  - placeholder LoRA adapters removed (they target the 31B model);
  - model alias set by --model.
Condition-specific changes are only the two paragraphs below plus the extra tool, so any difference
between conditions comes from the knowledge pack and/or the gates.
"""
import argparse
import re
import shutil
from pathlib import Path

SAMPLE = Path(r"F:\kaggle\gemma_agent\data\sample_submission")
OUT = Path(__file__).resolve().parent / "conditions"

KP_TEXT = """
## Offline Library Documentation
This sandbox has no internet access, so you cannot look up library documentation online.
- Use `search_api_docs` to find the right function of an installed library (numpy, xarray, pandas, ...)
  by describing what you need, and `search_api_docs(show="package.function")` to read its full docstring.
- Check the exact name and signature before calling a library function you are not sure about, and
  search again after any `AttributeError`, `TypeError: ... unexpected keyword argument`, or `ImportError`
  raised from library code.
"""

GATE_TEXT = """
## Pre-Submission Checks
`submit_patch` only accepts a patch that passes automatic checks:
- a reproduction script at `/tmp/repro.py` (keep it in /tmp, never in /workspace) that exits non-zero on
  the original code and exits 0 with your fix, e.g. by asserting the behaviour the issue asks for;
- no edits to test or config files, no stray files in /workspace;
- the changed code compiles and imports, and related existing tests do not start failing.
Write `/tmp/repro.py` before editing the source. If `submit_patch` reports a failed check, fix the reported
problem and submit again. After repeated failures the patch is withdrawn.
"""

TOOLS = ["run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"]


def base_prompt():
    text = (SAMPLE / "prompts/system.md").read_text(encoding="utf-8")
    old = ("- If the problem statement does not provide explicit file paths, use `search_similar_code` with keywords "
           "from the error message to locate relevant files efficiently, rather than running `find` or `grep` across the entire repo.")
    new = ("- If the problem statement does not provide explicit file paths, use a targeted `grep -rn` for the function, "
           "class or error message names under the package directory to locate the relevant files.")
    assert old in text, "official prompt changed; update make_conditions.py"
    return text.replace(old, new)


def write(cond, model, kp, gate):
    d = OUT / cond
    if d.exists():
        shutil.rmtree(d)
    (d / "prompts").mkdir(parents=True)
    (d / "configs").mkdir()
    prompt = base_prompt()
    anchor = "## Anti-Patterns to Avoid"
    extra = (KP_TEXT if kp else "") + (GATE_TEXT if gate else "")
    prompt = prompt.replace(anchor, extra.strip() + "\n\n" + anchor) if extra else prompt
    (d / "prompts/system.md").write_text(prompt, encoding="utf-8")
    # same sampling as the official sample, but max_output_tokens 8192: the local Ollama server caps output there
    sampling = (SAMPLE / "configs/sampling.yaml").read_text(encoding="utf-8").replace("max_output_tokens: 16384", "max_output_tokens: 8192")
    (d / "configs/sampling.yaml").write_text(sampling, encoding="utf-8")
    tools = TOOLS + (["search_api_docs"] if kp else [])
    yaml = [f"name: offline_{cond}_agent", f"model: {model}", "instruction: !include prompts/system.md", "tools:"]
    yaml += [f"  - {t}" for t in tools]
    yaml += ["generate_content_config: !include configs/sampling.yaml", ""]
    (d / "agent.yaml").write_text("\n".join(yaml), encoding="utf-8")
    return len(re.findall(r"\w+", prompt))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma-4-12b-it")
    a = ap.parse_args()
    for cond, kp, gate in [("base", 0, 0), ("kp", 1, 0), ("gate", 0, 1), ("kp_gate", 1, 1)]:
        print(cond, "prompt words:", write(cond, a.model, kp, gate))
