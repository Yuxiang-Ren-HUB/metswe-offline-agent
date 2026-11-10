"""Three restyled versions of Figure 1 (gate v2 flow) for the user to choose from; output in figures/atm/gate_flow_variants/.
Text content matches fig_gate_flow.png; Times New Roman, 5.45 in wide (text column), drawn in inch coordinates."""
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_style import save, use_style  # noqa: E402

use_style("en")
mpl.rcParams.update({"font.family": "Times New Roman", "mathtext.fontset": "stix"})
OUT = Path(__file__).resolve().parent / "atm" / "gate_flow_variants"
W = 5.45
INK, MUTED = "#222222", "#555555"
BLUE, RED, GREEN, GREY, AMBER = "#2B6CB0", "#B5534A", "#2F855A", "#6B7280", "#B7791F"
CHECKS = [("G1", "a source file changed", "hard"),
          ("G2", "no test or config edits", "hard"),
          ("G3", "files parse, modules import", "hard"),
          ("G4", "/tmp/repro.py fails before,\npasses with the patch", "hard / warn"),
          ("G5", "related tests gain no failures", "warn")]
REJECT = "G1–G3 fail, or the\nreproduction still fails\nwith the patch.\nAbstain after 3 tries\n(at once on fallback)."
SUBMIT = "Everything else. A missing\nor uninformative repro or a\nG5 failure is a warning:\nshown once on submit,\nignored on fallback."
TRIGGER = "agent calls\nsubmit_patch,\nor a budget\nruns out\n(fallback)"
REPAIR = "delete scratch\nand data files;\nrestore edited\ntest and config\nfiles"


def canvas(h):
    fig = plt.figure(figsize=(W, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def arrow(ax, p0, p1, color=MUTED, label=None, lxy=None, lw=1.1):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=10, lw=lw, color=color, shrinkA=0, shrinkB=0))
    if label:
        ax.text(*lxy, label, fontsize=8, color=color, ha="center", va="center", style="italic")


def badge(ax, x, y, text, color):
    ax.text(x, y, text, fontsize=7.5, color="white", ha="right", va="center",
            bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.08", fc=color, ec="none"))


# ---------- A: horizontal, coloured title bars ----------
SUBMIT_W = "Everything else. A\nmissing or uninformative\nrepro or a G5 failure is\na warning: shown once\non submit, ignored on\nfallback."
X_TRIG, X_REP, X_CHK, X_OUT = (0.03, 0.80), (0.95, 0.90), (2.02, 1.95), (4.12, 1.31)


def header_box(ax, x, y, w, h, title, color, tint):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06", fc=tint, ec=color, lw=0.9))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.27), w, 0.27, boxstyle="round,pad=0,rounding_size=0.06", fc=color, ec=color, lw=0.9))
    ax.add_patch(plt.Rectangle((x, y + h - 0.27), w, 0.1, fc=color, ec="none"))
    ax.text(x + 0.08, y + h - 0.135, title, fontsize=9, color="white", fontweight="bold", va="center")


def check_rows(ax, x0, x1, ytop, step, dots=False):
    for i, (g, txt, kind) in enumerate(CHECKS):
        yy = ytop - i * step
        ax.text(x0, yy, g, fontsize=8.5, fontweight="bold", color=BLUE if not dots else INK, va="center")
        ax.text(x0 + 0.25, yy, txt, fontsize=8, color=INK, va="center", linespacing=1.1)
        if dots:
            continue
        if kind == "hard / warn":
            badge(ax, x1, yy + 0.085, "hard", RED)
            badge(ax, x1, yy - 0.085, "warn", AMBER)
        else:
            badge(ax, x1, yy, kind, RED if kind == "hard" else AMBER)


def variant_a(path=None):
    H = 2.6
    fig, ax = canvas(H)
    y0, h = 0.25, 2.1
    header_box(ax, *X_TRIG[:1], y0, X_TRIG[1], h, "Trigger", GREY, "#F3F4F6")
    ax.text(X_TRIG[0] + 0.08, y0 + (h - 0.27) / 2, TRIGGER, fontsize=8.5, color=INK, va="center", linespacing=1.35)
    header_box(ax, X_REP[0], y0, X_REP[1], h, "1  Repair", BLUE, "#EBF2FA")
    ax.text(X_REP[0] + 0.08, y0 + (h - 0.27) / 2, REPAIR, fontsize=8.5, color=INK, va="center", linespacing=1.35)
    header_box(ax, X_CHK[0], y0, X_CHK[1], h, "2  Check", BLUE, "#EBF2FA")
    check_rows(ax, X_CHK[0] + 0.09, X_CHK[0] + X_CHK[1] - 0.06, y0 + h - 0.55, 0.35)
    header_box(ax, X_OUT[0], 1.38, X_OUT[1], 1.2, "Reject", RED, "#FBEDEB")
    ax.text(X_OUT[0] + 0.07, 2.25, REJECT, fontsize=7.8, color=INK, va="top", linespacing=1.22)
    header_box(ax, X_OUT[0], 0.02, X_OUT[1], 1.26, "Submit", GREEN, "#EAF5EE")
    ax.text(X_OUT[0] + 0.07, 0.95, SUBMIT_W, fontsize=7.8, color=INK, va="top", linespacing=1.22)
    ym = y0 + (h - 0.27) / 2
    arrow(ax, (X_TRIG[0] + X_TRIG[1] + 0.01, ym), (X_REP[0] - 0.01, ym))
    arrow(ax, (X_REP[0] + X_REP[1] + 0.01, ym), (X_CHK[0] - 0.01, ym))
    xe = X_CHK[0] + X_CHK[1] + 0.01
    arrow(ax, (xe, 1.75), (X_OUT[0] - 0.01, 2.0), RED)
    arrow(ax, (xe, 0.95), (X_OUT[0] - 0.01, 0.7), GREEN)
    save(fig, path or OUT / "A_header_bars.png")


# ---------- B: vertical flow ----------
def plain_box(ax, x, y, w, h, color, tint, lw=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc=tint, ec=color, lw=lw))


def variant_b():
    H = 4.1
    fig, ax = canvas(H)
    # top row: trigger -> repair
    plain_box(ax, 0.35, 3.35, 2.1, 0.62, GREY, "#F3F4F6")
    ax.text(0.47, 3.85, "Trigger", fontsize=9.5, fontweight="bold", color=INK, va="top")
    ax.text(0.47, 3.62, "agent calls submit_patch, or a\nbudget runs out (fallback)", fontsize=8.5, color=INK, va="top", linespacing=1.2)
    plain_box(ax, 3.0, 3.35, 2.1, 0.62, BLUE, "#EBF2FA")
    ax.text(3.12, 3.85, "1  Repair", fontsize=9.5, fontweight="bold", color=BLUE, va="top")
    ax.text(3.12, 3.62, "delete scratch and data files;\nrestore edited test and config files", fontsize=8.5, color=INK, va="top", linespacing=1.2)
    arrow(ax, (2.47, 3.66), (2.98, 3.66))
    # check box, full width
    plain_box(ax, 0.35, 1.62, 4.75, 1.45, BLUE, "#EBF2FA")
    ax.text(0.47, 2.97, "2  Check", fontsize=9.5, fontweight="bold", color=BLUE, va="top")
    arrow(ax, (4.05, 3.33), (4.05, 3.09))
    rows = [(g, t.replace("\n", " "), k) for g, t, k in CHECKS]
    for i, (g, txt, kind) in enumerate(rows):
        yy = 2.62 - i * 0.2
        ax.text(0.55, yy, g, fontsize=8.5, fontweight="bold", color=BLUE, va="center")
        ax.text(0.85, yy, txt, fontsize=8.5, color=INK, va="center")
        badge(ax, 4.98, yy, kind, RED if kind == "hard" else ("#B7791F" if kind == "warn" else "#8A5A44"))
    # outcomes
    plain_box(ax, 0.35, 0.33, 2.25, 0.9, RED, "#FBEDEB")
    ax.text(0.47, 1.13, "Reject", fontsize=9.5, fontweight="bold", color=RED, va="top")
    ax.text(0.47, 0.9, REJECT.replace("\n", " ").replace(". ", ".\n").replace("fails with", "fails\nwith"), fontsize=8.2, color=INK, va="top", linespacing=1.2)
    plain_box(ax, 2.85, 0.33, 2.25, 0.9, GREEN, "#EAF5EE")
    ax.text(2.97, 1.13, "Submit", fontsize=9.5, fontweight="bold", color=GREEN, va="top")
    ax.text(2.97, 0.9, "Everything else. A missing or\nuninformative repro or a G5\nfailure is a warning: shown once\non submit, ignored on fallback.", fontsize=8.2, color=INK, va="top", linespacing=1.2)
    arrow(ax, (1.48, 1.6), (1.48, 1.25), RED, "hard", (1.75, 1.42))
    arrow(ax, (3.98, 1.6), (3.98, 1.25), GREEN, "pass / warn", (4.42, 1.42))
    ax.set_ylim(0.25, H)
    fig.set_size_inches(W, H - 0.25)
    save(fig, OUT / "B_vertical.png")


# ---------- C: minimal outline, left accent bars ----------
def accent_box(ax, x, y, w, h, title, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05", fc="white", ec="#C9CED6", lw=0.8))
    ax.add_patch(plt.Rectangle((x, y + 0.03), 0.05, h - 0.06, fc=color, ec="none"))
    ax.text(x + 0.13, y + h - 0.1, title, fontsize=9.5, fontweight="bold", color=color, va="top")


def variant_c(path=None):
    H = 2.6
    fig, ax = canvas(H)
    accent_box(ax, X_TRIG[0], 0.45, X_TRIG[1], 1.7, "Trigger", GREY)
    ax.text(X_TRIG[0] + 0.12, 1.15, TRIGGER, fontsize=8.5, color=INK, va="center", linespacing=1.35)
    accent_box(ax, X_REP[0], 0.45, X_REP[1], 1.7, "1  Repair", BLUE)
    ax.text(X_REP[0] + 0.12, 1.15, REPAIR, fontsize=8.5, color=INK, va="center", linespacing=1.35)
    accent_box(ax, X_CHK[0], 0.02, X_CHK[1], 2.56, "2  Check", BLUE)
    for i, (g, txt, kind) in enumerate(CHECKS):
        yy = 2.05 - i * 0.37
        col = RED if kind == "hard" else (AMBER if kind == "warn" else None)
        if col:
            ax.add_patch(plt.Circle((X_CHK[0] + 0.19, yy), 0.035, color=col))
        else:
            ax.add_patch(mpl.patches.Wedge((X_CHK[0] + 0.19, yy), 0.035, 90, 270, color=RED))
            ax.add_patch(mpl.patches.Wedge((X_CHK[0] + 0.19, yy), 0.035, 270, 90, color=AMBER))
        ax.text(X_CHK[0] + 0.27, yy, g, fontsize=8.5, fontweight="bold", color=INK, va="center")
        ax.text(X_CHK[0] + 0.52, yy, txt, fontsize=8, color=INK, va="center", linespacing=1.1)
    lx = X_CHK[0] + 0.19
    ax.add_patch(plt.Circle((lx, 0.2), 0.03, color=RED))
    ax.text(lx + 0.07, 0.2, "hard failure", fontsize=7.5, color=MUTED, va="center")
    ax.add_patch(plt.Circle((lx + 0.85, 0.2), 0.03, color=AMBER))
    ax.text(lx + 0.92, 0.2, "warning", fontsize=7.5, color=MUTED, va="center")
    accent_box(ax, X_OUT[0], 1.38, X_OUT[1], 1.2, "Reject", RED)
    ax.text(X_OUT[0] + 0.12, 2.23, REJECT, fontsize=7.8, color=INK, va="top", linespacing=1.22)
    accent_box(ax, X_OUT[0], 0.02, X_OUT[1], 1.26, "Submit", GREEN)
    ax.text(X_OUT[0] + 0.12, 0.98, SUBMIT_W, fontsize=7.8, color=INK, va="top", linespacing=1.22)
    arrow(ax, (X_TRIG[0] + X_TRIG[1] + 0.01, 1.3), (X_REP[0] - 0.01, 1.3))
    arrow(ax, (X_REP[0] + X_REP[1] + 0.01, 1.3), (X_CHK[0] - 0.01, 1.3))
    xe = X_CHK[0] + X_CHK[1] + 0.01
    arrow(ax, (xe, 1.75), (X_OUT[0] - 0.01, 2.0), RED)
    arrow(ax, (xe, 0.95), (X_OUT[0] - 0.01, 0.7), GREEN)
    save(fig, path or OUT / "C_minimal.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    variant_a()
    variant_b()
    variant_c()
