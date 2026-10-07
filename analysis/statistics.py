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


def pareto_frontier(costs, rates) -> list[int]:
    """Indices of the points no cheaper (or equally cheap) point beats on
    pass rate, cheapest first: the best pass rate each budget can buy."""
    best = -math.inf
    frontier = []
    for i in sorted(range(len(costs)), key=lambda i: (costs[i], -rates[i])):
        if rates[i] > best:
            frontier.append(i)
            best = rates[i]
    return frontier


# Radar axes, in drawing order, with the label drawn for each (the figures
# are in Italian); every score runs 0 (worst) to 1 (best). Each suite gets its
# own radar: the two tasks differ too much to share one.
RADAR_AXES = {
    "accuracy": "accuratezza",
    "consistency": "coerenza",
    "speed": "velocità",
    "low_cost": "economicità",
}

# What "accuracy" measures in each suite (its pass criterion).
RADAR_ACCURACY_LABELS = {"markdown": "accuratezza\n(corrispondenza esatta)",
                         "sonar": "accuratezza\n(correzione pulita)"}

# Fixed log scales for the two unbounded measures: (value scoring 1, value
# scoring 0). Fixed rather than relative to the models compared, so a model's
# scores don't change when another model is added or dropped, and a 7x latency
# gap isn't stretched to fill the axis the way a 1000x cost gap does.
RADAR_LOG_SCALES = {
    "speed": (1.0, 60.0),        # mean latency per case, seconds
    "low_cost": (1e-4, 10.0),    # EUR for one repetition of the suite
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
    """One row per (model, suite): the raw measures behind each radar axis,
    the 0-1 score drawn for it, and the weighted task score (equal weights by
    default). There is no score across suites: averaging two very different
    tasks hides how a model does at either.

    Accuracy and consistency are absolute rates. Speed (mean latency per case)
    and cost (one repetition of the suite, from `cost_per_rep_eur`) use the
    fixed log scales in RADAR_LOG_SCALES."""
    weights = weights or {axis: 1.0 for axis in RADAR_AXES}
    columns = ["model", "group", "suite", "accuracy", "consistency", "latency_s", "cost_per_rep_eur"]
    scores = summary.assign(
        accuracy=summary["pass_rate"],
        consistency=summary["mean_agreement_rate"],
        latency_s=summary["latency_mean"],
        cost_per_rep_eur=summary["cost_per_rep_eur"] if "cost_per_rep_eur" in summary else math.nan,
    )[columns].reset_index(drop=True)
    if scores.empty:
        return scores
    scores["speed"] = _log_score(scores["latency_s"], *RADAR_LOG_SCALES["speed"])
    scores["low_cost"] = _log_score(scores["cost_per_rep_eur"], *RADAR_LOG_SCALES["low_cost"])
    total = sum(weights.values())
    scores["score"] = sum(scores[axis] * weight for axis, weight in weights.items()) / total
    return scores
