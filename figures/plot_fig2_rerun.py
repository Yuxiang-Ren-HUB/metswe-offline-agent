"""Figure 2: run 1 vs run 2 outcome of every task, for base and gate v2, reading only fig2_data.json."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_style import new_figure, save, use_style  # noqa: E402

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "fig2_data.json").read_text())
OUT = ["resolved", "wrong", "none"]
TICK = ["resolved", "wrong\npatch", "no\npatch"]
TITLE = {"base": "(a) base", "gate2": "(b) gate v2"}

use_style("en")
fig, axes = new_figure(height_in=2.9, ncols=2)
for ax, c in zip(axes, ["base", "gate2"]):
    m = np.array([[D[c][f"{x}|{y}"] for y in OUT] for x in OUT])
    assert m.sum() == 100
    ax.imshow(m, cmap="Blues", vmin=0, vmax=70)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(m[i, j]), ha="center", va="center", fontsize=9,
                    color="white" if m[i, j] > 40 else "#222222", fontweight="bold" if i == j else "normal")
    r1, r2 = D[c]["runs"]
    ax.set_xticks(range(3), [f"{t}\n({r2[o]})" for t, o in zip(TICK, OUT)])
    ax.set_yticks(range(3), [f"{t.replace(chr(10), ' ')} ({r1[o]})" for t, o in zip(TICK, OUT)])
    ax.set_xlabel("run 2")
    ax.set_ylabel("run 1" if c == "base" else "")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.text(0, 1.03, TITLE[c], transform=ax.transAxes, fontsize=9.5, ha="left", va="bottom")
save(fig, HERE / "fig2_rerun.png")
