"""论文插图统一样式。

用法：
    from paper_style import use_style, new_figure, save, sub_sup

    use_style("zh")                       # 中文学位论文：宋体 + Times New Roman
    fig, axes = new_figure(height_in=4.0, nrows=2)
    ...
    save(fig, "fig3-1.png")               # 300 dpi，宽度保持 6.1 in，并自动检查
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

FULL_WIDTH_IN = 6.1      # 15.5 cm，A4 版心通栏
DPI = 300

_BASE = {
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 9.5,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "lines.linewidth": 1.0,
    "axes.unicode_minus": True,
    "savefig.dpi": DPI,
    "figure.dpi": 100,
}


def use_style(lang="zh"):
    """lang='zh'：中文宋体 + 英文 Times New Roman；lang='en'：Arial 系无衬线。"""
    mpl.rcParams.update(_BASE)
    if lang == "zh":
        mpl.rcParams["font.family"] = ["Times New Roman", "SimSun"]
        mpl.rcParams["mathtext.fontset"] = "stix"
    elif lang == "en":
        mpl.rcParams["font.family"] = "sans-serif"
        mpl.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]
        mpl.rcParams["mathtext.fontset"] = "dejavusans"
    else:
        raise ValueError("lang 只能是 'zh' 或 'en'")


def new_figure(height_in, nrows=1, ncols=1, width_in=FULL_WIDTH_IN, **kw):
    """按印刷尺寸建图。默认通栏 6.1 in 宽；多子图优先上下排（nrows>1）。"""
    kw.setdefault("layout", "constrained")
    return plt.subplots(nrows, ncols, figsize=(width_in, height_in), **kw)


def save(fig, path, expect_width_in=None):
    """固定 300 dpi 保存，不用 bbox_inches='tight'（会改变宽度），保存后核对物理宽度。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    w_in = fig.get_figwidth()
    target = expect_width_in or FULL_WIDTH_IN
    print(f"[paper_style] {path.name}: {w_in:.2f} in = {w_in * 2.54:.1f} cm @ {DPI} dpi")
    if abs(w_in - target) > 0.05:
        print(f"[paper_style] 注意：宽度不是 {target} in，插入 Word 时会被缩放，字号会跟着变")
    return path


_SUP = str.maketrans("0123456789+-−=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿ")
_SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")


def sub_sup(text):
    """把 'PM_{10}'、'm^{-2}' 写法转成 Unicode 上下标，用于含汉字的标签（避免 mathtext 缺字）。

    >>> sub_sup("PM_{2.5} 浓度 (μg m^{-3})")  # 小数点没有下标字符，会原样保留
    """
    import re

    text = re.sub(r"\^\{([^}]*)\}", lambda m: m.group(1).translate(_SUP), text)
    text = re.sub(r"_\{([^}]*)\}", lambda m: m.group(1).translate(_SUB), text)
    return text
