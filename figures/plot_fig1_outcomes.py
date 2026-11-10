"""Figure 1: per-condition outcomes (resolved / wrong patch / no patch), reading only fig_data.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_style import new_figure, save, use_style  # noqa: E402

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "fig_data.json").read_text())
LABEL = {"base": "base", "kp": "knowledge pack", "gate": "gate v1", "kp_gate": "knowledge pack + gate v1", "gate2": "gate v2"}
COLORS = {"resolved": "#2b7a3d", "wrong": "#c8553d", "none": "#c9c9c9"}
NAMES = {"resolved": "resolved", "wrong": "wrong patch submitted", "none": "no patch (abstained or no edit)"}

use_style("en")
fig, axes = new_figure(height_in=3.6, nrows=2, gridspec_kw={"height_ratios": [3, 5]})
panels = [("all", ["base", "kp", "gate2"], "(a) MetSWE-100"),
          ("dev", ["base", "kp", "gate", "kp_gate", "gate2"], "(b) Development set (47 tasks)")]
for ax, (key, conds, title) in zip(axes, panels):
    rows = list(reversed(conds))
    for y, c in enumerate(rows):
        s = D["sets"][key][c]
        left = 0
        for part in ("resolved", "wrong", "none"):
            v = s[part] / s["n"] * 100
            ax.barh(y, v, left=left, color=COLORS[part], height=0.62, edgecolor="white", linewidth=0.5,
                    label=NAMES[part] if (key == "all" and y == 0) else None)
            if s[part] >= 3:
                ax.text(left + v / 2, y, str(s[part]), ha="center", va="center", fontsize=8,
                        color="white" if part != "none" else "#333333")
            left += v
        prec = s["resolved"] / s["submitted"]
        ax.text(101.5, y, f"{prec:.2f}", ha="left", va="center", fontsize=8.5)
    ax.set_yticks(range(len(rows)), [LABEL[c] for c in rows])
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of tasks (%)" if key == "dev" else "")
    ax.text(0, 1.04, title, transform=ax.transAxes, fontsize=9.5, ha="left", va="bottom")
    ax.text(1.0, 1.04, "precision", transform=ax.transAxes, fontsize=8.5, ha="left", va="bottom")
    ax.spines[["top", "right"]].set_visible(False)
fig.legend(loc="outside upper center", ncols=3, frameon=False, fontsize=8.5)
save(fig, HERE / "fig1_outcomes.png")
