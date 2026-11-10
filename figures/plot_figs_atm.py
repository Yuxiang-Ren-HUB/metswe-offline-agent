"""English figures in Times New Roman, drawn at the text-column width (5.45 in) of the MDPI layout; output in figures/atm/."""
import json
import sys
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_style import new_figure, save, use_style  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "atm"
WIDTH = 5.45
use_style("en")
mpl.rcParams.update({"font.family": "Times New Roman", "mathtext.fontset": "stix"})

# Figure 1: gate v2 flow (style C, chosen 2026-11-10; drawn in plot_gate_flow_variants.py)
from plot_gate_flow_variants import variant_c  # noqa: E402

variant_c(OUT / "fig_gate_flow.png")

# Figure 2: outcomes in every run
D = json.loads((HERE / "fig_ablation_data.json").read_text())
PARTS = [("resolved", "Resolved", "#2B6CB0", "white"), ("failing", "Failing patch", "#D9822B", "#222222"), ("none", "No patch", "#52B69A", "#222222")]
Y = [0, 0.82, 1.92, 3.02, 3.84, 4.94]
fig, ax = new_figure(height_in=2.45, width_in=WIDTH)
for y, d in zip(Y, D):
    assert sum(d[k] for k, *_ in PARTS) == 100
    left = 0
    for k, lab, col, ink in PARTS:
        ax.barh(y, d[k], left=left, height=0.7, color=col, edgecolor="white", linewidth=1.2)
        ax.text(left + d[k] / 2, y, str(d[k]), ha="center", va="center", fontsize=9, color=ink)
        left += d[k]
ax.set_yticks(Y, [d["label"] for d in D])
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.set_xlabel("Tasks (of 100)")
ax.tick_params(axis="y", length=0)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.legend(list(ax.containers[:3]), [p[1] for p in PARTS], loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=3, frameon=False, fontsize=9)
save(fig, OUT / "fig_ablation.png")

# Figure 3: run 1 against run 2
R = json.loads((HERE / "fig2_data.json").read_text())
KEYS = ["resolved", "wrong", "none"]
TICK = ["resolved", "failing\npatch", "no\npatch"]
fig, axes = new_figure(height_in=2.7, ncols=2, width_in=WIDTH)
for ax, c, title in zip(axes, ["base", "gate2"], ["(a) base", "(b) gate v2"]):
    m = np.array([[R[c][f"{x}|{y}"] for y in KEYS] for x in KEYS])
    assert m.sum() == 100
    ax.imshow(m, cmap="Blues", vmin=0, vmax=70)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(m[i, j]), ha="center", va="center", fontsize=9, color="white" if m[i, j] > 40 else "#222222", fontweight="bold" if i == j else "normal")
    r1, r2 = R[c]["runs"]
    ax.set_xticks(range(3), [f"{t}\n({r2[o]})" for t, o in zip(TICK, KEYS)])
    ax.set_yticks(range(3), [f"{t.replace(chr(10), ' ')} ({r1[o]})" for t, o in zip(TICK, KEYS)])
    ax.set_xlabel("run 2")
    ax.set_ylabel("run 1" if c == "base" else "")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.text(0, 1.03, title, transform=ax.transAxes, fontsize=9.5, ha="left", va="bottom")
save(fig, OUT / "fig2_rerun.png")
