"""
matplotlib/seaborn figures for reproducibility runs.

Every function takes the tidy frames from analysis/aggregate.py (or
analysis/statistics.py) and returns a Figure; saving is left to the caller
(`save`). Two families:

  single run   classification_breakdown, pass_matrix, repetition_pass_rate,
               case_stability, sonar_stage_funnel, latency_tokens,
               markdown_by_difficulty
  comparison   pass_rate_comparison, classification_comparison,
               case_pass_heatmap, agreement_distribution,
               sonar_funnel_comparison, efficiency_scatter,
               group_summary_plot

Colours are fixed roles, never assigned by rank: the case classifications
use an ordinal blue ramp for the three stable levels with orange for flaky
and grey for harness errors; groups are blue (commercial) / orange (open
source); sonar stages are an ordinal blue ramp for where a trial stopped,
with green for the one passing stage. Each palette was checked
with the dataviz skill's validator (CVD separation, contrast, monotone
lightness). Identity is always backed by a legend or an axis label.
"""

import math
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, to_rgb  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, MaxNLocator, NullFormatter, PercentFormatter  # noqa: E402

from analysis.aggregate import COMMERCIAL, GROUPS, OPEN_SOURCE, SONAR_STAGES, UNKNOWN  # noqa: E402
from analysis.statistics import CLASSIFICATION_ORDER, FUNNEL_STAGES, GROUP_METRICS, RADAR_AXES  # noqa: E402

# --------------------------------------------------------------------------- #
# palette and style
# --------------------------------------------------------------------------- #

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
NEUTRAL = "#e1e0d9"

# Categorical slots, in fixed order (never cycled).
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")

BLUE_RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281")

CLASSIFICATION_COLORS = {
    "identical": "#184f95",
    "equivalent": "#3987e5",
    "outcome-stable": "#86b6ef",
    "flaky": "#eb6834",
    "harness-error": INK_MUTED,
}

GROUP_COLORS = {COMMERCIAL: SERIES[0], OPEN_SOURCE: SERIES[1], UNKNOWN: INK_MUTED}
GROUP_MARKERS = {COMMERCIAL: "o", OPEN_SOURCE: "s", UNKNOWN: "D"}

STAGE_COLORS = {
    "not_applied": BASELINE,
    "applied": "#86b6ef",
    "compiled": "#3987e5",
    "tests_passed": "#1c5cab",
    "resolved": "#0d366b",
    # The one passing stage: status "good", so it never reads as a further
    # shade of "stopped here".
    "clean_fix": "#0ca30c",
}
STAGE_LABELS = {
    "not_applied": "not applied",
    "applied": "applied",
    "compiled": "compiled",
    "tests_passed": "tests passed",
    "resolved": "issue resolved",
    "clean_fix": "clean fix",
}

PASS_COLOR = SERIES[0]
FAIL_COLOR = NEUTRAL
ERROR_COLOR = SERIES[1]

SEQUENTIAL = LinearSegmentedColormap.from_list("repro_blues", BLUE_RAMP)

SUITE_LABELS = {"markdown": "Markdown extraction", "sonar": "Sonar fixes"}
CRITERION_LABELS = {"matched": "exact JSON match", "clean_fix": "clean fix", "tests_passed": "tests passed"}

BAR_HEIGHT = 0.62


def apply_style() -> None:
    sns.set_theme(style="whitegrid", font_scale=0.95)
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BASELINE,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titleweight": "bold",
        "axes.titlesize": 11,
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelcolor": INK_SECONDARY,
        "ytick.labelcolor": INK_SECONDARY,
        "text.color": INK,
        "legend.frameon": False,
        "legend.labelcolor": INK_SECONDARY,
        "lines.linewidth": 2,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "font.family": "sans-serif",
    })


apply_style()


def save(fig: plt.Figure, out_dir: Path, name: str, fmt: str = "png", dpi: int = 200) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.{fmt}"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _suites(frame: pd.DataFrame) -> list[str]:
    present = list(dict.fromkeys(frame["suite"]))
    return [s for s in ("markdown", "sonar") if s in present] + [s for s in present if s not in ("markdown", "sonar")]


def _suite_title(suite: str, criterion: str | None = None) -> str:
    title = SUITE_LABELS.get(suite, suite)
    if criterion:
        title += f"  ·  pass = {CRITERION_LABELS.get(criterion, criterion)}"
    return title


def _pct(rate: float) -> str:
    """Whole percent, except that a rate that isn't exactly 0 or 1 never
    rounds to 0% or 100% (199/200 is not 100%)."""
    text = f"{rate:.0%}"
    if (text == "100%" and rate < 1) or (text == "0%" and rate > 0):
        text = f"{rate:.1%}"
    return text


def _ink_for(color: str) -> str:
    """White or ink, whichever reads on this fill."""
    r, g, b = to_rgb(color)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return INK if luminance > 0.55 else "white"


def _percent_axis(axis, *, x: bool) -> None:
    formatter = PercentFormatter(1.0, decimals=0)
    (axis.xaxis if x else axis.yaxis).set_major_formatter(formatter)


def _finish_with_legend(fig: plt.Figure, handles, ncol: int | None = None, note: str | None = None,
                        h_pad: float | None = None) -> None:
    """Lay the figure out with a legend row (or rows) reserved underneath,
    and optionally a muted footnote under that (e.g. cost assumptions)."""
    handles = list(handles)
    ncol = ncol or max(len(handles), 1)
    rows = math.ceil(len(handles) / ncol)
    # 7.5 pt footnote lines are ~0.15 in apart.
    note_height = 0.15 * len(note.splitlines()) + 0.05 if note else 0.0
    bottom = (0.3 * rows + note_height + 0.15) / fig.get_figheight()
    fig.tight_layout(rect=(0, bottom, 1, 1), h_pad=h_pad)
    if handles:
        fig.legend(
            handles=handles,
            loc="lower center",
            bbox_to_anchor=(0.5, (note_height + 0.03) / fig.get_figheight()),
            ncol=ncol,
            handlelength=1.0,
            handleheight=1.0,
            columnspacing=1.4,
        )
    if note:
        fig.text(0.01, 0.01, note, ha="left", va="bottom", fontsize=7.5, color=INK_MUTED)


def _patches(colors: dict, labels: dict | None = None, keys=None) -> list[Patch]:
    keys = keys if keys is not None else colors.keys()
    return [Patch(facecolor=colors[k], edgecolor="none", label=(labels or {}).get(k, k)) for k in keys]


def _stacked_hbar(ax, frame: pd.DataFrame, order: list[str], colors: dict, *, as_share: bool, min_label: float) -> None:
    """Horizontal stacked bars: frame index = bar labels (top to bottom),
    columns = segment keys in `order`. Segments are separated by a thin
    surface-coloured gap; counts are labelled only where they fit."""
    totals = frame[order].sum(axis=1).replace(0, np.nan)
    values = frame[order].div(totals, axis=0) if as_share else frame[order]
    y = np.arange(len(frame))[::-1]
    left = np.zeros(len(frame))
    for key in order:
        widths = values[key].fillna(0).to_numpy()
        ax.barh(y, widths, left=left, height=BAR_HEIGHT, color=colors[key],
                edgecolor=SURFACE, linewidth=1.2, label=key)
        for yi, li, wi, count in zip(y, left, widths, frame[key].to_numpy()):
            if wi >= min_label and count:
                ax.text(li + wi / 2, yi, f"{int(count)}", ha="center", va="center",
                        fontsize=8, color=_ink_for(colors[key]))
        left += widths
    ax.set_yticks(y)
    ax.set_yticklabels(frame.index)
    ax.grid(axis="y", visible=False)


# --------------------------------------------------------------------------- #
# single run
# --------------------------------------------------------------------------- #


def classification_breakdown(cases: pd.DataFrame, title: str) -> plt.Figure:
    """Share of cases in each reproducibility class, one bar per suite."""
    suites = _suites(cases)
    counts = (
        cases.groupby("suite")["classification"].value_counts().unstack(fill_value=0)
        .reindex(index=suites, columns=CLASSIFICATION_ORDER, fill_value=0)
    )
    counts.index = [SUITE_LABELS.get(s, s) for s in counts.index]

    fig, ax = plt.subplots(figsize=(8, 1.1 + 0.7 * len(suites)))
    _stacked_hbar(ax, counts, list(CLASSIFICATION_ORDER), CLASSIFICATION_COLORS, as_share=True, min_label=0.04)
    ax.set_xlim(0, 1)
    _percent_axis(ax, x=True)
    ax.set_xlabel("share of cases (segment labels = number of cases)")
    ax.set_title(title)
    _finish_with_legend(fig, _patches(CLASSIFICATION_COLORS))
    return fig


def pass_matrix(reps: pd.DataFrame, title: str) -> plt.Figure:
    """Cases x repetitions: pass, fail or harness error. A deterministic
    case is a solid row; a flaky one is striped."""
    suites = _suites(reps)
    height = max(len(reps[reps["suite"] == s]["case_id"].unique()) for s in suites)
    fig, axes = plt.subplots(1, len(suites), figsize=(5.2 * len(suites), 1.4 + 0.28 * height), squeeze=False)
    cmap = ListedColormap([FAIL_COLOR, PASS_COLOR, ERROR_COLOR])

    for ax, suite in zip(axes[0], suites):
        frame = reps[reps["suite"] == suite]
        code = np.where(frame["harness_error"], 2, frame["passed"].fillna(0))
        matrix = (
            frame.assign(code=code)
            .pivot_table(index="case_id", columns="rep", values="code", aggfunc="first")
            .sort_index()
        )
        sns.heatmap(matrix, ax=ax, cmap=cmap, vmin=-0.5, vmax=2.5, cbar=False,
                    linewidths=1.2, linecolor=SURFACE, square=False)
        passes = frame.groupby("case_id")["passed"].agg(["sum", "count"]).reindex(matrix.index)
        for i, (k, n) in enumerate(passes.itertuples(index=False)):
            ax.text(matrix.shape[1] + 0.25, i + 0.5, f"{int(k)}/{int(n)}", va="center", fontsize=8, color=INK_SECONDARY)
        ax.set_title(SUITE_LABELS.get(suite, suite))
        ax.set_xlabel("repetition")
        ax.set_ylabel("")
        ax.tick_params(axis="both", length=0)
        ax.tick_params(axis="y", labelrotation=0)

    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, [
        Patch(facecolor=PASS_COLOR, label="pass"),
        Patch(facecolor=FAIL_COLOR, label="fail"),
        Patch(facecolor=ERROR_COLOR, label="harness error (excluded)"),
    ])
    return fig


def repetition_pass_rate(rates: pd.DataFrame, suites_meta: pd.DataFrame, title: str) -> plt.Figure:
    """Each repetition's pass rate with the mean and a +/-1 stdev band."""
    suites = _suites(rates)
    fig, axes = plt.subplots(1, len(suites), figsize=(5.2 * len(suites), 3.4), squeeze=False, sharey=True)
    for ax, suite in zip(axes[0], suites):
        frame = rates[rates["suite"] == suite].sort_values("rep")
        meta = suites_meta[suites_meta["suite"] == suite].iloc[0]
        mean, stdev = meta["rep_pass_rate_mean"], meta["rep_pass_rate_stdev"] or 0.0
        ax.axhspan(mean - stdev, mean + stdev, color=PASS_COLOR, alpha=0.10, linewidth=0)
        ax.axhline(mean, color=INK_MUTED, linewidth=1)
        ax.plot(frame["rep"], frame["pass_rate"], color=PASS_COLOR, marker="o", markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.text(frame["rep"].max() + 0.35, mean, f"mean {_pct(mean)}", va="center", fontsize=8, color=INK_SECONDARY,
                bbox={"boxstyle": "square,pad=0.15", "facecolor": SURFACE, "edgecolor": "none"})
        ax.set_title(f"{SUITE_LABELS.get(suite, suite)}  ·  sd {stdev * 100:.1f} pp")
        ax.set_xticks(frame["rep"])
        ax.set_xlim(frame["rep"].min() - 0.5, frame["rep"].max() + 1.8)
        ax.set_xlabel("repetition")
        ax.grid(axis="x", visible=False)
        _percent_axis(ax, x=False)
    axes[0][0].set_ylabel("pass rate (band = ±1 sd)")
    low = min(0.0, float(rates["pass_rate"].min()))
    axes[0][0].set_ylim(low, 1.05)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def case_stability(cases: pd.DataFrame, title: str) -> plt.Figure:
    """Per case: share of repetitions giving the most common output, coloured
    by classification, labelled with the number of distinct outputs."""
    suites = _suites(cases)
    height = max((cases["suite"] == s).sum() for s in suites)
    fig, axes = plt.subplots(1, len(suites), figsize=(5.2 * len(suites), 1.4 + 0.28 * height), squeeze=False)
    for ax, suite in zip(axes[0], suites):
        frame = cases[cases["suite"] == suite].sort_values("case_id", ascending=False)
        y = np.arange(len(frame))
        ax.barh(y, frame["agreement_rate"], height=BAR_HEIGHT,
                color=[CLASSIFICATION_COLORS.get(c, INK_MUTED) for c in frame["classification"]])
        for yi, rate, outputs, raw in zip(y, frame["agreement_rate"], frame["distinct_effective_outputs"],
                                          frame["distinct_raw_outputs"]):
            label = f"{outputs} output{'s' if outputs != 1 else ''}"
            if raw != outputs:
                label += f" ({raw} raw)"
            ax.text(min(rate, 1) + 0.02, yi, label, va="center", fontsize=7.5, color=INK_SECONDARY)
        ax.set_yticks(y)
        ax.set_yticklabels(frame["case_id"])
        ax.set_xlim(0, 1.45)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        _percent_axis(ax, x=True)
        ax.set_xlabel("agreement (reps giving the most common effective output)")
        ax.grid(axis="y", visible=False)
        ax.set_title(SUITE_LABELS.get(suite, suite))
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    present = [c for c in CLASSIFICATION_ORDER if c in set(cases["classification"])]
    _finish_with_legend(fig, _patches(CLASSIFICATION_COLORS, keys=present))
    return fig


def sonar_stage_funnel(stages: pd.DataFrame, funnel: pd.DataFrame, title: str) -> plt.Figure:
    """Left: share of all sonar trials reaching each stage. Right: where each
    case's repetitions stopped."""
    by_case = stages.pivot_table(index="case_id", columns="stage", values="count", aggfunc="sum", fill_value=0)
    by_case = by_case.reindex(columns=list(SONAR_STAGES), fill_value=0).sort_index()
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(11, 1.4 + 0.28 * len(by_case)), gridspec_kw={"width_ratios": [1, 1.6]}
    )

    frame = funnel.set_index("stage").reindex(list(FUNNEL_STAGES))
    y = np.arange(len(frame))[::-1]
    left.barh(y, frame["rate"], height=BAR_HEIGHT, color=PASS_COLOR)
    for yi, rate, reached, trials in zip(y, frame["rate"], frame["reached"], frame["trials"]):
        left.text(rate + 0.02, yi, f"{_pct(rate)}  ({int(reached)}/{int(trials)})", va="center", fontsize=8,
                  color=INK_SECONDARY)
    left.set_yticks(y)
    left.set_yticklabels([STAGE_LABELS[s] for s in FUNNEL_STAGES])
    left.set_xlim(0, 1.45)
    left.set_xticks([0, 0.25, 0.5, 0.75, 1])
    _percent_axis(left, x=True)
    left.set_xlabel("share of trials reaching the stage")
    left.grid(axis="y", visible=False)
    left.set_title("Pipeline funnel")

    _stacked_hbar(right, by_case, list(SONAR_STAGES), STAGE_COLORS, as_share=False, min_label=1)
    right.set_xlabel("repetitions, by the last stage cleared")
    right.set_title("Where each case stopped")
    right.xaxis.get_major_locator().set_params(integer=True)

    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, _patches(STAGE_COLORS, STAGE_LABELS))
    return fig


def latency_tokens(reps: pd.DataFrame, title: str) -> plt.Figure:
    """Per case, across repetitions: latency and completion tokens. Two
    measures, two panels - never one dual axis."""
    reps = reps[~reps["harness_error"]]
    suites = _suites(reps)
    height = max(reps[reps["suite"] == s]["case_id"].nunique() for s in suites)
    fig, axes = plt.subplots(len(suites), 2, figsize=(11, (1.2 + 0.26 * height) * len(suites)), squeeze=False)
    metrics = (("execution_time", "latency (s)"), ("completion_tokens", "completion tokens"))
    for row, suite in zip(axes, suites):
        frame = reps[reps["suite"] == suite].sort_values("case_id")
        for ax, (column, label) in zip(row, metrics):
            sns.boxplot(data=frame, y="case_id", x=column, ax=ax, color=BLUE_RAMP[1], width=0.55,
                        linewidth=0.8, fliersize=0, boxprops={"edgecolor": INK_MUTED},
                        whiskerprops={"color": INK_MUTED}, capprops={"color": INK_MUTED},
                        medianprops={"color": INK})
            sns.stripplot(data=frame, y="case_id", x=column, ax=ax, color=PASS_COLOR, size=3.5, jitter=0.18,
                          linewidth=0.6, edgecolor=SURFACE)
            ax.set_ylabel("")
            ax.set_xlabel(label)
            ax.set_xlim(left=0)
            ax.grid(axis="y", visible=False)
            ax.set_title(f"{SUITE_LABELS.get(suite, suite)} · {label}")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def markdown_by_difficulty(cases: pd.DataFrame, title: str) -> plt.Figure | None:
    """Markdown mean per-case pass rate by difficulty, and by category when
    categories group several cases (one case per category says nothing the
    pass matrix doesn't)."""
    frame = cases[cases["suite"] == "markdown"]
    if frame.empty or frame["difficulty"].isna().all():
        return None
    panels = [("difficulty", "difficulty")]
    categories = frame["category"].dropna()
    if not categories.empty and categories.nunique() < len(categories):
        panels.append(("category", "category"))
    fig, axes = plt.subplots(1, len(panels), figsize=(5.5 * len(panels), 3.6), squeeze=False)
    for ax, (column, label) in zip(axes[0], panels):
        grouped = frame.dropna(subset=[column]).groupby(column)["pass_rate"].agg(["mean", "count"])
        if column == "difficulty":
            grouped.index = [f"level {int(d)}" for d in grouped.index]
        y = np.arange(len(grouped))[::-1]
        ax.barh(y, grouped["mean"], height=BAR_HEIGHT, color=PASS_COLOR)
        for yi, mean, count in zip(y, grouped["mean"], grouped["count"]):
            ax.text(mean + 0.02, yi, f"{_pct(mean)}  (n={count})", va="center", fontsize=8, color=INK_SECONDARY)
        ax.set_yticks(y)
        ax.set_yticklabels(grouped.index)
        ax.set_xlim(0, 1.3)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        _percent_axis(ax, x=True)
        ax.set_xlabel("mean per-case pass rate")
        ax.grid(axis="y", visible=False)
        ax.set_title(f"By {label}")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# comparison
# --------------------------------------------------------------------------- #


def model_order(frame: pd.DataFrame) -> list[str]:
    """Commercial models first, then open source, alphabetical within each."""
    pairs = frame[["model", "group"]].drop_duplicates()
    rank = {g: i for i, g in enumerate(GROUPS)}
    return [m for m, _g in sorted(pairs.itertuples(index=False), key=lambda p: (rank.get(p[1], 99), p[0].lower()))]


def model_labels(frame: pd.DataFrame) -> dict[str, str]:
    groups = frame[["model", "group"]].drop_duplicates().set_index("model")["group"]
    short = {COMMERCIAL: "commercial", OPEN_SOURCE: "open source", UNKNOWN: "unknown"}
    return {m: f"{m}\n{short.get(g, g)}" for m, g in groups.items()}


def _group_handles(frame: pd.DataFrame) -> list[Patch]:
    present = [g for g in GROUPS if g in set(frame["group"])]
    return [Patch(facecolor=GROUP_COLORS[g], label=g) for g in present]


def pass_rate_comparison(summary: pd.DataFrame) -> plt.Figure:
    """Pooled pass rate per model with a 95% Wilson interval, per suite."""
    suites = _suites(summary)
    order = model_order(summary)
    labels = model_labels(summary)
    fig, axes = plt.subplots(1, len(suites), figsize=(5.4 * len(suites), 1.4 + 0.62 * len(order)),
                             squeeze=False, sharey=True)
    for ax, suite in zip(axes[0], suites):
        frame = summary[summary["suite"] == suite].set_index("model").reindex(order)
        y = np.arange(len(order))[::-1]
        ax.barh(y, frame["pass_rate"], height=BAR_HEIGHT, color=[GROUP_COLORS.get(g, INK_MUTED) for g in frame["group"]])
        low = (frame["pass_rate"] - frame["pass_rate_ci_low"]).clip(lower=0)
        high = (frame["pass_rate_ci_high"] - frame["pass_rate"]).clip(lower=0)
        ax.errorbar(frame["pass_rate"], y, xerr=[low, high], fmt="none", ecolor=INK, elinewidth=1, capsize=3)
        for yi, rate, top, passes, trials in zip(y, frame["pass_rate"], frame["pass_rate_ci_high"],
                                                 frame["passes"], frame["trials"]):
            if not math.isnan(rate):
                ax.text(top + 0.03, yi, f"{_pct(rate)}  ({int(passes)}/{int(trials)})", va="center",
                        fontsize=8, color=INK_SECONDARY)
        ax.set_yticks(y)
        ax.set_yticklabels([labels[m] for m in order])
        ax.set_xlim(0, 1.4)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        _percent_axis(ax, x=True)
        ax.set_xlabel("pass rate over all trials (95% Wilson CI)")
        ax.grid(axis="y", visible=False)
        criterion = frame["criterion"].dropna().iloc[0] if frame["criterion"].notna().any() else None
        ax.set_title(_suite_title(suite, criterion))
    fig.suptitle("Pass rate: commercial vs open-source models", x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, _group_handles(summary))
    return fig


def classification_comparison(cases: pd.DataFrame) -> plt.Figure:
    """Share of cases per reproducibility class, one bar per model."""
    suites = _suites(cases)
    order = model_order(cases)
    labels = model_labels(cases)
    fig, axes = plt.subplots(1, len(suites), figsize=(5.4 * len(suites), 1.4 + 0.62 * len(order)),
                             squeeze=False, sharey=True)
    for ax, suite in zip(axes[0], suites):
        counts = (
            cases[cases["suite"] == suite].groupby("model")["classification"].value_counts()
            .unstack(fill_value=0).reindex(index=order, columns=CLASSIFICATION_ORDER, fill_value=0)
        )
        counts.index = [labels[m] for m in counts.index]
        _stacked_hbar(ax, counts, list(CLASSIFICATION_ORDER), CLASSIFICATION_COLORS, as_share=True, min_label=0.04)
        ax.set_xlim(0, 1)
        _percent_axis(ax, x=True)
        ax.set_xlabel("share of cases (labels = number of cases)")
        ax.set_title(SUITE_LABELS.get(suite, suite))
    fig.suptitle("How reproducible each model is", x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, _patches(CLASSIFICATION_COLORS))
    return fig


def case_pass_heatmap(cases: pd.DataFrame) -> plt.Figure:
    """Models x cases, cell = that case's pass rate across repetitions."""
    suites = _suites(cases)
    order = model_order(cases)
    labels = model_labels(cases)
    fig, axes = plt.subplots(len(suites), 1, figsize=(11, (1.3 + 0.55 * len(order)) * len(suites)), squeeze=False)
    for (ax,), suite in zip(axes, suites):
        matrix = (
            cases[cases["suite"] == suite]
            .pivot_table(index="model", columns="case_id", values="pass_rate", aggfunc="first")
            .reindex(order)
        )
        matrix.index = [labels[m].replace("\n", " · ") for m in matrix.index]
        sns.heatmap(matrix, ax=ax, cmap=SEQUENTIAL, vmin=0, vmax=1, linewidths=1.2, linecolor=SURFACE,
                    cbar_kws={"format": PercentFormatter(1.0, decimals=0), "label": "pass rate", "shrink": 0.9})
        ax.set_title(SUITE_LABELS.get(suite, suite))
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="both", length=0)
        ax.tick_params(axis="x", labelrotation=90)
        ax.tick_params(axis="y", labelrotation=0)
    fig.suptitle("Per-case pass rate across repetitions", x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def agreement_distribution(cases: pd.DataFrame) -> plt.Figure:
    """Distribution of per-case agreement rates for each model."""
    suites = _suites(cases)
    order = model_order(cases)
    labels = model_labels(cases)
    fig, axes = plt.subplots(1, len(suites), figsize=(5.4 * len(suites), 1.6 + 0.95 * len(order)),
                             squeeze=False, sharey=True)
    for ax, suite in zip(axes[0], suites):
        frame = cases[cases["suite"] == suite]
        sns.boxplot(data=frame, y="model", x="agreement_rate", order=order, ax=ax, color=GRID, width=0.5,
                    linewidth=0.8, fliersize=0, boxprops={"edgecolor": INK_MUTED},
                    whiskerprops={"color": INK_MUTED}, capprops={"color": INK_MUTED}, medianprops={"color": INK})
        sns.stripplot(data=frame, y="model", x="agreement_rate", order=order, hue="group", ax=ax,
                      palette=GROUP_COLORS, size=5, jitter=0.2, linewidth=0.8, edgecolor=SURFACE, legend=False)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([labels[m] for m in order])
        ax.set_xlim(-0.02, 1.05)
        _percent_axis(ax, x=True)
        ax.set_xlabel("per-case agreement across reps")
        ax.set_ylabel("")
        ax.grid(axis="y", visible=False)
        ax.set_title(SUITE_LABELS.get(suite, suite))
    fig.suptitle("Output agreement across repetitions", x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, _group_handles(cases))
    return fig


FUNNEL_SHORT_LABELS = {"applied": "applied", "compiled": "compiled", "tests_passed": "tests",
                       "resolved": "resolved", "clean_fix": "clean fix"}


def sonar_funnel_comparison(funnel: pd.DataFrame) -> plt.Figure:
    """Share of sonar trials reaching each pipeline stage: one small panel
    per model, its own line in its group colour over every other model's
    in faint grey. Identity comes from the panel title, not from telling
    nine-plus colours apart, so it stays readable however many models
    there are."""
    order = model_order(funnel)
    ncols = 3 if len(order) <= 9 else 4
    nrows = math.ceil(len(order) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 2.5 * nrows + 0.6),
                             sharex=True, sharey=True, squeeze=False)
    x = np.arange(len(FUNNEL_STAGES))
    rates = {
        model: funnel[funnel["model"] == model].set_index("stage").reindex(list(FUNNEL_STAGES))
        for model in order
    }

    for ax, model in zip(axes.flat, order):
        for other in order:
            if other != model:
                ax.plot(x, rates[other]["rate"], color=BASELINE, linewidth=1, alpha=0.7, zorder=1)
        frame = rates[model]
        group = frame["group"].dropna().iloc[0]
        ax.plot(x, frame["rate"], color=GROUP_COLORS.get(group, INK_MUTED), marker=GROUP_MARKERS.get(group, "o"),
                markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=3)
        end = frame["rate"].iloc[-1]
        ax.annotate(_pct(end), (x[-1], end), xytext=(0, 7 if end < 0.9 else -13), textcoords="offset points",
                    ha="center", fontsize=8, color=INK_SECONDARY)
        ax.set_title(f"{model}\n{group.lower()}", fontsize=9, loc="left")
        ax.set_ylim(0, 1.08)
        ax.grid(axis="x", visible=False)
        _percent_axis(ax, x=False)

    for ax in axes.flat[len(order):]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("trials reaching stage")
    # The last visible panel in each column carries the stage labels.
    for column in range(ncols):
        visible = [axes[row, column] for row in range(nrows) if axes[row, column].get_visible()]
        if visible:
            visible[-1].set_xticks(x)
            visible[-1].set_xticklabels([FUNNEL_SHORT_LABELS[s] for s in FUNNEL_STAGES], rotation=35, ha="right")
            visible[-1].tick_params(axis="x", labelbottom=True)

    fig.suptitle("Sonar pipeline funnel by model  (label = clean-fix rate)", x=0.01, ha="left",
                 fontweight="bold", color=INK)
    present = [g for g in GROUPS if g in set(funnel["group"])]
    handles = [Line2D([], [], color=GROUP_COLORS[g], marker=GROUP_MARKERS[g], markersize=6, label=g) for g in present]
    handles.append(Line2D([], [], color=BASELINE, linewidth=1, label="other models"))
    _finish_with_legend(fig, handles)
    return fig


def _spread(positions: list[float], gap: float, low: float = 0.0, high: float = 1.0) -> list[float]:
    """Nudge sorted label positions apart to at least `gap`, staying within
    [low, high] - as close to where they started as that allows."""
    placed = list(positions)
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + gap)
    if placed and placed[-1] > high:
        placed[-1] = high
        for i in range(len(placed) - 2, -1, -1):
            placed[i] = min(placed[i], placed[i + 1] - gap)
    if placed and placed[0] < low:  # too many labels for the height: space them evenly
        step = (high - low) / max(len(placed) - 1, 1)
        placed = [low + i * step for i in range(len(placed))]
    return placed


def _label_column(ax, fig: plt.Figure, xs, ys, labels, y_top: float) -> None:
    """Label points from a column just right of the axes, one leader line
    each: labels can't collide however the points cluster."""
    height_in = ax.get_position().height * fig.get_figheight()
    order = sorted(range(len(labels)), key=lambda i: ys[i])
    targets = _spread([ys[i] / y_top for i in order], gap=0.16 / height_in)
    for i, target in zip(order, targets):
        ax.annotate(labels[i], (xs[i], ys[i]), xytext=(1.04, target), textcoords="axes fraction",
                    va="center", fontsize=8, color=INK_SECONDARY, annotation_clip=False,
                    arrowprops={"arrowstyle": "-", "color": BASELINE, "linewidth": 0.8,
                                "shrinkA": 2, "shrinkB": 5})


def efficiency_scatter(summary: pd.DataFrame) -> plt.Figure:
    """Pass rate against cost: mean latency (top) and mean completion tokens
    (bottom), per suite. Separate panels, one scale each."""
    suites = _suites(summary)
    fig, axes = plt.subplots(2, len(suites), figsize=(7.0 * len(suites), 7.6), squeeze=False)
    metrics = (("latency_mean", "mean latency per case (s, log scale)"),
               ("tokens_mean", "mean completion tokens per case (log scale)"))
    for row, (column, label) in zip(axes, metrics):
        for ax, suite in zip(row, suites):
            frame = summary[summary["suite"] == suite]
            for group, sub in frame.groupby("group"):
                ax.scatter(sub[column], sub["pass_rate"], s=70, color=GROUP_COLORS.get(group, INK_MUTED),
                           marker=GROUP_MARKERS.get(group, "o"), edgecolor=SURFACE, linewidth=1.5, zorder=3)
            ax.set_xscale("log")
            ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:g}"))
            ax.xaxis.set_minor_formatter(NullFormatter())
            ax.set_ylim(0, 1.08)
            _percent_axis(ax, x=False)
            ax.set_xlabel(label)
            ax.set_ylabel("pass rate")
            ax.set_title(SUITE_LABELS.get(suite, suite))
            lo, hi = frame[column].min(), frame[column].max()
            if lo > 0 and hi > 0:
                ax.set_xlim(lo / 2, hi * 2)
            labelled = frame.dropna(subset=[column, "pass_rate"])
            _label_column(ax, fig, labelled[column].tolist(), labelled["pass_rate"].tolist(),
                          labelled["model"].tolist(), y_top=1.08)
    fig.suptitle("Accuracy vs cost", x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, _group_handles(summary))
    return fig


def group_summary_plot(summary: pd.DataFrame, groups: pd.DataFrame) -> plt.Figure:
    """Commercial vs open source: group mean per metric (bars) with each
    model's own value overlaid, so a group of one visibly is one model."""
    suites = _suites(summary)
    metrics = list(GROUP_METRICS)
    present = [g for g in GROUPS if g in set(summary["group"])]
    fig, axes = plt.subplots(1, len(suites), figsize=(5.8 * len(suites), 4.2), squeeze=False, sharey=True)
    width = min(0.8 / max(len(present), 1), 0.36)
    for ax, suite in zip(axes[0], suites):
        x = np.arange(len(metrics))
        for i, group in enumerate(present):
            offset = (i - (len(present) - 1) / 2) * width
            row = groups[(groups["suite"] == suite) & (groups["group"] == group)]
            values = [row[m].iloc[0] if not row.empty else np.nan for m in metrics]
            ax.bar(x + offset, values, width=width * 0.92, color=GROUP_COLORS[group], alpha=0.35, linewidth=0)
            models = summary[(summary["suite"] == suite) & (summary["group"] == group)]
            for j, metric in enumerate(metrics):
                ax.scatter(np.full(len(models), x[j] + offset), models[metric], s=36, color=GROUP_COLORS[group],
                           marker=GROUP_MARKERS[group], edgecolor=SURFACE, linewidth=1.2, zorder=3)
            for xi, value in zip(x + offset, values):
                if not np.isnan(value):
                    ax.text(xi, value + 0.025, _pct(value), ha="center", fontsize=7.5, color=INK_SECONDARY)
        ax.set_xticks(x)
        ax.set_xticklabels([GROUP_METRICS[m].replace(" ", "\n", 1) for m in metrics])
        ax.set_ylim(0, 1.12)
        _percent_axis(ax, x=False)
        ax.grid(axis="x", visible=False)
        ax.set_title(SUITE_LABELS.get(suite, suite))
    counts = summary.drop_duplicates("model")["group"].value_counts()
    legend = [Patch(facecolor=GROUP_COLORS[g], alpha=0.6, label=f"{g} (mean of {counts.get(g, 0)} model"
                    f"{'s' if counts.get(g, 0) != 1 else ''}; markers = individual models)") for g in present]
    fig.suptitle("Commercial vs open source", x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, legend, ncol=1)
    return fig


# --------------------------------------------------------------------------- #
# cost
# --------------------------------------------------------------------------- #


def _euro_tick(value: float, _pos=None) -> str:
    """Plain decimals, no trailing zeros: €0, €0.05, €0.01, €1. Rounded to
    six significant figures first, so float noise from the tick locator
    (6.000000000000001e-05) never reaches the label."""
    return f"€{np.format_float_positional(float(f'{value:.6g}'), trim='-')}"


def _cost_scale(largest: float) -> int:
    """Attempts per unit for a cost axis: 1, 1,000 or 1,000,000 - the first
    that puts the largest value at or above €0.10, so labels stay short
    instead of trailing strings of leading zeros."""
    for scale in (1, 1_000, 1_000_000):
        if largest * scale >= 0.1:
            return scale
    return 1_000_000


def _wrap_note(note: str) -> str:
    """Cost notes join their parts with ' · '; one part per line."""
    return "\n".join(note.split("  ·  "))


def cost_by_case(trials: pd.DataFrame, title: str, note: str) -> plt.Figure | None:
    """Mean cost of one attempt at each case, per suite; the whisker is the
    power-draw band for electricity-costed runs."""
    from analysis.costs import format_eur

    trials = trials.dropna(subset=["cost_eur"])
    if trials.empty:
        return None
    suites = _suites(trials)
    height = max(trials[trials["suite"] == s]["case_id"].nunique() for s in suites)
    columns = ["cost_eur", "cost_eur_low", "cost_eur_high"]
    # One scale for every panel, so the suites stay comparable.
    scale = _cost_scale(trials.groupby(["suite", "case_id"])["cost_eur_high"].mean().max())
    unit = "attempt" if scale == 1 else f"{scale:,} attempts"
    fig, axes = plt.subplots(1, len(suites), figsize=(5.4 * len(suites), 1.8 + 0.28 * height), squeeze=False)
    for ax, suite in zip(axes[0], suites):
        frame = trials[trials["suite"] == suite]
        per_rep = frame.groupby("rep")["cost_eur"].sum().mean()
        per_case = frame.groupby("case_id")[columns].mean().sort_index(ascending=False) * scale
        y = np.arange(len(per_case))
        ax.barh(y, per_case["cost_eur"], height=BAR_HEIGHT, color=PASS_COLOR)
        banded = (per_case["cost_eur_high"] - per_case["cost_eur_low"]) > 0
        if banded.any():
            ax.errorbar(per_case["cost_eur"], y,
                        xerr=[per_case["cost_eur"] - per_case["cost_eur_low"],
                              per_case["cost_eur_high"] - per_case["cost_eur"]],
                        fmt="none", ecolor=INK_MUTED, elinewidth=1, capsize=2)
        tips = per_case["cost_eur_high"].where(banded, per_case["cost_eur"])
        for yi, value, tip in zip(y, per_case["cost_eur"], tips):
            ax.text(tip * 1.02 + per_case["cost_eur_high"].max() * 0.01, yi, format_eur(value),
                    va="center", fontsize=7.5, color=INK_SECONDARY)
        ax.set_yticks(y)
        ax.set_yticklabels(per_case.index)
        ax.set_xlim(0, per_case["cost_eur_high"].max() * 1.35)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.xaxis.set_major_formatter(FuncFormatter(_euro_tick))
        ax.set_xlabel(f"mean cost per {unit}")
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{SUITE_LABELS.get(suite, suite)}  ·  {format_eur(per_rep)} per repetition")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, [], note=_wrap_note(note))
    return fig


def cost_comparison(costs: pd.DataFrame, note: str) -> plt.Figure:
    """What one repetition of each suite costs per model, and what one
    passing trial costs, on a log scale (API and electricity costs sit
    orders of magnitude apart). Whiskers = the local power-draw band."""
    from analysis.costs import format_eur

    suites = _suites(costs)
    order = model_order(costs)
    basis_labels = {"api": "API fees", "gpu-hours": "rented GPU time", "electricity-measured": "own GPU, measured",
                    "electricity": "own GPU, assumed", "unpriced": "unpriced"}
    labels = {
        model: f"{text}\n" + " + ".join(basis_labels.get(b, b) for b in basis.split("/"))
        for model, text, basis in (
            (model, text.split("\n")[0], costs[costs["model"] == model]["cost_basis"].iloc[0])
            for model, text in model_labels(costs).items()
        )
    }
    metrics = (("cost_per_rep_eur", "cost of one full suite repetition"),
               ("cost_per_pass_eur", "cost per passing trial"))
    fig, axes = plt.subplots(len(metrics), len(suites), figsize=(5.6 * len(suites), (1.5 + 0.6 * len(order)) * 2),
                             squeeze=False, sharey=True)
    positive = costs[[m + s for m, _l in metrics for s in ("_low", "_high", "")]].to_numpy().ravel()
    positive = positive[np.isfinite(positive) & (positive > 0)]
    lo, hi = (positive.min() / 4, positive.max() * 12) if positive.size else (1e-4, 1)

    for row, (column, label) in zip(axes, metrics):
        for ax, suite in zip(row, suites):
            frame = costs[costs["suite"] == suite].set_index("model").reindex(order)
            y = np.arange(len(order))[::-1]
            for yi, (model, r) in zip(y, frame.iterrows()):
                color = GROUP_COLORS.get(r["group"], INK_MUTED)
                value, low, high = r[column], r[column + "_low"], r[column + "_high"]
                if not np.isfinite(value):
                    text = "no passing trials" if column == "cost_per_pass_eur" else "no price"
                    ax.text(lo * 1.2, yi, text, va="center", fontsize=8, color=INK_MUTED)
                    continue
                if high > low:
                    ax.plot([low, high], [yi, yi], color=color, linewidth=2.5, alpha=0.45, solid_capstyle="round")
                ax.scatter([value], [yi], s=70, color=color, marker=GROUP_MARKERS.get(r["group"], "o"),
                           edgecolor=SURFACE, linewidth=1.5, zorder=3)
                ax.annotate(format_eur(value), (max(value, high if high > low else value), yi), xytext=(7, 0),
                            textcoords="offset points", va="center", fontsize=8, color=INK_SECONDARY)
            ax.set_xscale("log")
            ax.set_xlim(lo, hi)
            # A label every second decade keeps six decades legible; the
            # decades in between still get a gridline.
            ax.xaxis.set_major_locator(LogLocator(base=100))
            ax.xaxis.set_minor_locator(LogLocator(base=10))
            ax.xaxis.set_major_formatter(FuncFormatter(_euro_tick))
            ax.xaxis.set_minor_formatter(NullFormatter())
            ax.grid(axis="x", which="minor", color=GRID, linewidth=0.8)
            ax.set_yticks(y)
            ax.set_yticklabels([labels[m] for m in order])
            ax.set_ylim(-0.6, len(order) - 0.4)
            ax.set_xlabel(f"{label} (log scale)")
            ax.grid(axis="y", visible=False)
            ax.set_title(SUITE_LABELS.get(suite, suite))
    fig.suptitle("What a run costs  (label: how each model is priced)", x=0.01, ha="left", fontweight="bold", color=INK)
    _finish_with_legend(fig, _group_handles(costs), note=_wrap_note(note))
    return fig


# --------------------------------------------------------------------------- #
# model selection
# --------------------------------------------------------------------------- #


def radar_note(weights: dict[str, float] | None = None) -> str:
    from analysis.statistics import RADAR_LOG_SCALES

    (fast, slow), (cheap, dear) = RADAR_LOG_SCALES["speed"], RADAR_LOG_SCALES["low_cost"]
    if weights is None or len(set(weights.values())) == 1:
        overall = "Overall = unweighted mean of the five."
    else:
        overall = "Overall = weighted mean (" + ", ".join(
            f"{RADAR_AXES[a].replace(chr(10), ' ')} {w:g}" for a, w in weights.items()) + ")."
    return (
        "Outer = better. Markdown accuracy and sonar clean fixes: share of all trials passed.  "
        "Consistency: share of repetitions giving a case's most common output, averaged over both suites.  "
        f"Speed: mean latency per case on a log scale, {fast:g} s at the rim to {slow:g} s at the centre.  "
        f"Low cost: one repetition of both suites on a log scale, \u20ac{cheap:g} at the rim to "
        f"\u20ac{dear:g} at the centre.  {overall}  "
        "Costs mix API fees, rented GPU time and own-GPU electricity (see the cost figure); "
        "latency mixes API, H200 and laptop hardware."
    )


def radar_comparison(scores: pd.DataFrame, weights: dict[str, float] | None = None) -> plt.Figure:
    """One radar per model - quality, consistency, speed and cost on axes
    where outer is always better - ranked by overall score, each drawn over
    every other model's outline in grey so a panel reads on its own and
    against the field. `scores` comes from statistics.radar_scores."""
    axes_keys = list(RADAR_AXES)
    angles = np.linspace(0, 2 * np.pi, len(axes_keys), endpoint=False)
    closed = np.append(angles, angles[0])

    def outline(row) -> np.ndarray:
        values = row[axes_keys].astype(float).fillna(0).to_numpy()
        return np.append(values, values[0])

    count = len(scores)
    ncols = 3 if count <= 9 else 4
    nrows = math.ceil(count / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.8 * ncols, 4.2 * nrows + 1.2),
                             subplot_kw={"projection": "polar"}, squeeze=False)
    for rank, (ax, (_index, row)) in enumerate(zip(axes.flat, scores.iterrows()), start=1):
        for _other_index, other in scores.iterrows():
            if other["model"] != row["model"]:
                ax.plot(closed, outline(other), color=BASELINE, linewidth=0.8, alpha=0.8, zorder=1)
        color = GROUP_COLORS.get(row["group"], INK_MUTED)
        values = outline(row)
        ax.fill(closed, values, color=color, alpha=0.12, zorder=2)
        ax.plot(closed, values, color=color, linewidth=2, zorder=3)
        ax.scatter(angles, values[:-1], s=22, color=color, edgecolor=SURFACE, linewidth=1, zorder=4)

        ax.set_ylim(0, 1)
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels([])
        ax.set_xticks(angles)
        ax.set_xticklabels([RADAR_AXES[k] for k in axes_keys], fontsize=7.5, color=INK_SECONDARY)
        ax.tick_params(axis="x", pad=1)
        ax.grid(color=GRID, linewidth=0.8)
        ax.spines["polar"].set_color(GRID)
        ax.set_theta_offset(np.pi / 2)  # first axis at the top
        ax.set_theta_direction(-1)
        overall = "n/a" if pd.isna(row["overall"]) else f"{row['overall']:.2f}"
        ax.set_title(f"#{rank}  {row['model']}\n{row['group'].lower()} · overall {overall}",
                     fontsize=9, loc="center", pad=22)
    for ax in axes.flat[count:]:
        ax.set_visible(False)

    fig.suptitle("Which model to pick: quality, consistency, speed and cost  (ranked by overall score)",
                 x=0.01, ha="left", fontweight="bold", color=INK)
    present = [g for g in GROUPS if g in set(scores["group"])]
    handles = [Patch(facecolor=GROUP_COLORS[g], alpha=0.6, label=g) for g in present]
    handles.append(Line2D([], [], color=BASELINE, linewidth=1, label="other models"))
    # ~14 characters of 7.5 pt text per inch of figure width.
    note = "\n".join(textwrap.wrap(radar_note(weights), width=int(fig.get_figwidth() * 14)))
    # Polar tick labels sit outside the axes box tight_layout measures, so
    # rows need extra room to keep them clear of the next row's titles.
    _finish_with_legend(fig, handles, note=note, h_pad=4.5)
    # The suptitle needs its own band above the first row's (padded) titles.
    fig.subplots_adjust(top=fig.subplotpars.top - 0.45 / fig.get_figheight())
    return fig
