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


# Radar axes, in drawing order; every score runs 0 (worst) to 1 (best).
RADAR_AXES = {
    "markdown_accuracy": "markdown\naccuracy",
    "sonar_clean_fix": "sonar\nclean fixes",
    "consistency": "consistency",
    "speed": "speed",
    "low_cost": "low cost",
}

# Fixed log scales for the two unbounded measures: (value scoring 1, value
# scoring 0). Fixed rather than relative to the models compared, so a model's
# scores don't change when another model is added or dropped, and a 7x latency
# gap isn't stretched to fill the axis the way a 1000x cost gap does.
RADAR_LOG_SCALES = {
    "speed": (1.0, 60.0),        # mean latency per case, seconds
    "low_cost": (1e-4, 10.0),    # EUR for one repetition of both suites
}


def _log_score(values: pd.Series, best: float, worst: float) -> pd.Series:
    """1 at `best`, 0 at `worst`, log-spaced between, clipped to [0, 1]."""
    logs = values.where(values > 0).map(math.log)
    return ((math.log(worst) - logs) / (math.log(worst) - math.log(best))).clip(0, 1)


def parse_radar_weights(values: list[str] | None) -> dict[str, float]:
    """`--radar-weight AXIS=W` arguments -> {axis: weight}; unnamed axes keep 1."""
    weights = {axis: 1.0 for axis in RADAR_AXES}
    for value in values or []:
        axis, _, weight = value.partition("=")
        try:
            weights[axis.strip()] = float(weight)
        except ValueError:
            raise ValueError(f"Bad --radar-weight '{value}': expected AXIS=NUMBER") from None
        if axis.strip() not in RADAR_AXES or weights[axis.strip()] < 0:
            raise ValueError(f"Bad --radar-weight '{value}': axis must be one of {', '.join(RADAR_AXES)}, "
                             "weight >= 0")
    if not any(weights.values()):
        raise ValueError("--radar-weight: at least one axis needs a positive weight")
    return weights


def radar_scores(summary: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """One row per model: the raw measures behind each radar axis, the 0-1
    score drawn for it, and the weighted overall score (equal weights by
    default), most to least.

    Quality and consistency are absolute rates. Speed (mean latency per case
    across both suites) and cost (one repetition of both suites, from
    `cost_per_rep_eur`) use the fixed log scales in RADAR_LOG_SCALES."""
    weights = weights or {axis: 1.0 for axis in RADAR_AXES}
    rows = []
    for (model, group), frame in summary.groupby(["model", "group"], sort=False):
        by_suite = frame.set_index("suite")
        rate = lambda suite: by_suite["pass_rate"].get(suite, math.nan)
        costs = by_suite["cost_per_rep_eur"] if "cost_per_rep_eur" in by_suite else pd.Series(dtype=float)
        rows.append({
            "model": model,
            "group": group,
            "markdown_accuracy": rate("markdown"),
            "sonar_clean_fix": rate("sonar"),
            "consistency": by_suite["mean_agreement_rate"].mean(),
            "latency_s": by_suite["latency_mean"].mean(),
            # NaN unless every suite has a price: a partial sum would look cheap.
            "cost_per_rep_eur": costs.sum() if len(costs) and costs.notna().all() else math.nan,
        })
    scores = pd.DataFrame(rows)
    if scores.empty:
        return scores
    scores["speed"] = _log_score(scores["latency_s"], *RADAR_LOG_SCALES["speed"])
    scores["low_cost"] = _log_score(scores["cost_per_rep_eur"], *RADAR_LOG_SCALES["low_cost"])
    total = sum(weights.values())
    scores["overall"] = sum(scores[axis] * weight for axis, weight in weights.items()) / total
    return scores.sort_values("overall", ascending=False, na_position="last").reset_index(drop=True)
