"""
Derived metrics over the tidy frames built in analysis/aggregate.py.

Pass rates are pooled over every (case, repetition) trial, with a Wilson
score interval: with 20 cases x 10 repetitions the rates sit near 0 or 1,
where the normal-approximation interval collapses or leaves [0, 1].
"""

import math

import pandas as pd

from analysis.aggregate import SONAR_STAGES

# Classifications from runner/reproducibility/aggregate.py, most stable first.
CLASSIFICATION_ORDER = ("identical", "equivalent", "outcome-stable", "flaky", "harness-error")

# "Reached at least this stage" for the sonar funnel, skipping not_applied.
FUNNEL_STAGES = SONAR_STAGES[1:]


def wilson_interval(passes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if not trials:
        return math.nan, math.nan
    p = passes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def reproducibility_scores(cases: pd.DataFrame) -> pd.DataFrame:
    """Per (model, group, suite): how many cases fall into each
    classification, as shares, plus the mean agreement rate."""
    rows = []
    for (model, group, suite), frame in cases.groupby(["model", "group", "suite"], sort=False):
        total = len(frame)
        counts = frame["classification"].value_counts()
        share = {name: counts.get(name, 0) / total if total else math.nan for name in CLASSIFICATION_ORDER}
        rows.append({
            "model": model,
            "group": group,
            "suite": suite,
            "cases": total,
            **{f"share_{name}": value for name, value in share.items()},
            # Same answer every time, byte-for-byte or after normalisation.
            "share_stable_output": share["identical"] + share["equivalent"],
            "mean_agreement_rate": frame["agreement_rate"].mean(),
            "mean_distinct_outputs": frame["distinct_effective_outputs"].mean(),
            "latency_mean": frame["latency_mean"].mean(),
            "tokens_mean": frame["tokens_mean"].mean(),
        })
    return pd.DataFrame(rows)


def summary_table(suites: pd.DataFrame, cases: pd.DataFrame) -> pd.DataFrame:
    """Per (model, suite): pooled pass rate with its Wilson interval, the
    aggregate's pass/stability counts and the reproducibility shares."""
    table = suites.copy()
    table["pass_rate"] = table["passes"] / table["trials"]
    bounds = [wilson_interval(p, n) for p, n in zip(table["passes"], table["trials"])]
    table["pass_rate_ci_low"] = [low for low, _high in bounds]
    table["pass_rate_ci_high"] = [high for _low, high in bounds]
    scores = reproducibility_scores(cases).drop(columns=["group", "cases"])
    return table.merge(scores, on=["model", "suite"], how="left")


def funnel_rates(stages: pd.DataFrame) -> pd.DataFrame:
    """Per model: share of sonar trials that reached at least each stage."""
    rows = []
    for (model, group), frame in stages.groupby(["model", "group"], sort=False):
        counts = frame.groupby("stage")["count"].sum()
        total = counts.sum()
        for i, stage in enumerate(FUNNEL_STAGES):
            reached = sum(counts.get(s, 0) for s in SONAR_STAGES[i + 1:])
            rows.append({
                "model": model,
                "group": group,
                "stage": stage,
                "reached": reached,
                "trials": total,
                "rate": reached / total if total else math.nan,
            })
    return pd.DataFrame(rows, columns=["model", "group", "stage", "reached", "trials", "rate"])


GROUP_METRICS = {
    "pass_rate": "Pass rate",
    "share_stable_output": "Same output every rep",
    "share_flaky": "Flaky cases",
    "mean_agreement_rate": "Mean agreement",
}


def group_summary(summary: pd.DataFrame) -> pd.DataFrame:
    """Per (group, suite): the mean of each model's metrics - every model
    counts once, however many cases or repetitions its run had."""
    columns = list(GROUP_METRICS) + ["latency_mean", "tokens_mean"]
    columns += [c for c in ("cost_per_rep_eur", "cost_per_pass_eur") if c in summary.columns]
    grouped = summary.groupby(["group", "suite"], sort=False)
    result = grouped[columns].mean()
    result["models"] = grouped["model"].nunique()
    return result.reset_index()
