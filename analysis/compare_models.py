"""
Compare commercial and open-source models on their latest full
reproducibility runs.

For every model (a config name without its "(markdown)"/"(sonar)" suffix;
quantizations are separate models) the newest *full* run is selected: both
suites, every case, every repetition completed, sonar graded on clean fixes
(see analysis/aggregate.py:is_full_run). A model's group comes from the
provider in its configs/*.yaml - openai is commercial, llama.cpp is open
source - and can be overridden with --group.

Writes, under <results dir>/comparisons/<utc timestamp>/ by default:

    pass_rate           pooled pass rate per model with 95% Wilson CI
    classification      reproducibility classes per model
    case_heatmap        per-case pass rate, models x cases
    agreement           distribution of per-case output agreement
    sonar_funnel        share of sonar trials reaching each pipeline stage
    efficiency          pass rate vs latency and completion tokens
    group_summary       commercial vs open-source group means
    radar               one radar per model - markdown accuracy, sonar clean
                        fixes, consistency, speed, low cost - ranked by an
                        overall score, to help pick a model
    cost                cost of one suite repetition and of one passing trial:
                        API fees, or electricity for local models
    summary.csv         the numbers behind the figures, per model x suite
    radar_scores.csv    the raw measures and 0-1 scores behind the radar
    costs.csv           token, energy and cost totals, per model x suite
    cost_assumptions.json  prices, exchange rate and power draw used, with sources
    selected_runs.json  which run each model's numbers came from

Costs are in euros: OpenAI list prices for API models, electricity (inference
time x an assumed power draw x the ARERA household price) for local ones. See
analysis/costs.py for the prices and how to override them.

Usage:
    python -m analysis.compare_models --list        # every run, and which get selected
    python -m analysis.compare_models
    python -m analysis.compare_models --models GPT-5 Gemma-4-E4B-Q4-UD --format pdf
    python -m analysis.compare_models --results-dir results/04-10-26-all_models   # runs moved into a folder
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import aggregate as agg
from analysis import costs as cost
from analysis import statistics as stats
from runner.filesystem.paths import RESULTS_DIR


SUMMARY_COLUMNS = [
    "model", "group", "suite", "run_id", "criterion", "repetitions", "total_cases", "trials", "passes",
    "pass_rate", "pass_rate_ci_low", "pass_rate_ci_high", "rep_pass_rate_mean", "rep_pass_rate_stdev",
    "pass_all", "pass_any", "pass_none",
    "share_identical", "share_equivalent", "share_outcome-stable", "share_flaky", "share_harness-error",
    "share_stable_output", "mean_agreement_rate", "mean_distinct_outputs", "latency_mean", "tokens_mean",
    "cost_basis", "cost_per_rep_eur", "cost_per_pass_eur",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare commercial and open-source models on their latest full reproducibility runs."
    )
    parser.add_argument("--models", nargs="+", metavar="NAME", help="Only these models (default: every model).")
    parser.add_argument(
        "--group",
        action="append",
        metavar="MODEL=commercial|open",
        help="Override the commercial/open-source group of a model (repeatable).",
    )
    parser.add_argument("--results-dir", type=Path,
                        help="Where to look for reproducibility runs (default: results/). Use it when runs "
                             "have been moved into a subfolder, e.g. results/04-10-26-all_models.")
    parser.add_argument("--out", type=Path,
                        help="Output directory (default: <results dir>/comparisons/<timestamp>/).")
    parser.add_argument("--format", choices=("png", "pdf", "svg"), default="png", help="Image format (default: png).")
    parser.add_argument("--dpi", type=int, default=200, help="Raster resolution (default: 200).")
    parser.add_argument("--list", action="store_true", help="List reproducibility runs and the selection, then exit.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Explain why runs were skipped.")
    parser.add_argument(
        "--radar-weight", action="append", metavar="AXIS=W",
        help="Weight of a radar axis in the overall score (default: all 1). Axes: "
             + ", ".join(stats.RADAR_AXES) + ". Repeatable, e.g. --radar-weight sonar_clean_fix=2.",
    )
    cost.add_cost_arguments(parser)
    return parser.parse_args()


def print_listing(refs: list[agg.RunRef], selected: list[agg.RunRef], results_dir: Path = RESULTS_DIR) -> None:
    if not refs:
        print(f"No reproducibility runs under {results_dir}.")
        return
    chosen = {ref.run_id for ref in selected}
    width = max(21, *(len(ref.run_id) + 1 for ref in refs))
    print(f"{'':2}{'Run':<{width}} {'Model':<28} {'Group':<12} {'Reps':<5} {'Edit mode':<11} Status")
    for ref in refs:
        mark = "*" if ref.run_id in chosen else ""
        status = "full" if ref.full else f"partial: {ref.reason}"
        if ref.full and not mark:
            status += " (superseded by a newer run)"
        print(
            f"{mark:<2}{ref.run_id:<{width}} {ref.model:<28} {ref.group:<12} "
            f"{str(ref.settings.get('repetitions', '')):<5} {str(ref.settings.get('edit_mode', '')):<11} {status}"
        )
    print("\n* = selected for the comparison (newest full run per model)")


def build_frames(selected: list[agg.RunRef], assumptions: cost.CostAssumptions | None = None,
                 providers: dict[str, str] | None = None, model_ids: dict[str, str] | None = None,
                 radar_weights: dict[str, float] | None = None) -> dict[str, pd.DataFrame]:
    assumptions = assumptions or cost.CostAssumptions()
    cases = pd.concat([agg.case_frame(ref) for ref in selected], ignore_index=True)
    suites = pd.concat([agg.suite_frame(ref) for ref in selected], ignore_index=True)
    stages = pd.concat([agg.stage_frame(ref) for ref in selected], ignore_index=True)
    providers = agg.model_catalog() if providers is None else providers
    model_ids = agg.api_model_ids() if model_ids is None else model_ids
    trials = pd.concat([cost.trial_costs(ref, assumptions, providers, model_ids) for ref in selected],
                       ignore_index=True)
    summary = stats.summary_table(suites, cases)
    costs = cost.cost_summary(trials, summary)
    summary = summary.merge(
        costs[["model", "suite", "cost_basis", "cost_per_rep_eur", "cost_per_pass_eur"]],
        on=["model", "suite"], how="left",
    )
    return {
        "cases": cases,
        "summary": summary,
        "stages": stages,
        "funnel": stats.funnel_rates(stages),
        "groups": stats.group_summary(summary),
        "costs": costs,
        "radar": stats.radar_scores(summary, radar_weights),
    }


def plot_comparison(frames: dict[str, pd.DataFrame], out_dir: Path, fmt: str = "png", dpi: int = 200,
                    assumptions: cost.CostAssumptions | None = None,
                    radar_weights: dict[str, float] | None = None) -> list[Path]:
    from analysis import plots

    assumptions = assumptions or cost.CostAssumptions()

    cases, summary = frames["cases"], frames["summary"]
    figures = {
        "pass_rate": plots.pass_rate_comparison(summary),
        "classification": plots.classification_comparison(cases),
        "case_heatmap": plots.case_pass_heatmap(cases),
        "agreement": plots.agreement_distribution(cases),
        "efficiency": plots.efficiency_scatter(summary),
        "group_summary": plots.group_summary_plot(summary, frames["groups"]),
    }
    if not frames["funnel"].empty:
        figures["sonar_funnel"] = plots.sonar_funnel_comparison(frames["funnel"])
    costs = frames["costs"]
    if not costs.empty and costs["cost_per_rep_eur"].notna().any():
        bases = {b for basis in costs["cost_basis"] for b in basis.split("/")}
        figures["cost"] = plots.cost_comparison(costs, assumptions.note(bases))
    if not frames["radar"].empty:
        figures["radar"] = plots.radar_comparison(frames["radar"], radar_weights)
    return [plots.save(fig, out_dir, name, fmt, dpi) for name, fig in figures.items()]


def write_tables(frames: dict[str, pd.DataFrame], selected: list[agg.RunRef], out_dir: Path,
                 assumptions: cost.CostAssumptions | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = frames["summary"]
    columns = [c for c in SUMMARY_COLUMNS if c in summary.columns]
    summary_path = out_dir / "summary.csv"
    summary[columns].to_csv(summary_path, index=False, float_format="%.4f")

    groups_path = out_dir / "group_summary.csv"
    frames["groups"].to_csv(groups_path, index=False, float_format="%.4f")

    costs_path = out_dir / "costs.csv"
    frames["costs"].to_csv(costs_path, index=False, float_format="%.6g")

    radar_path = out_dir / "radar_scores.csv"
    frames["radar"].to_csv(radar_path, index=False, float_format="%.6g")

    assumptions_path = out_dir / "cost_assumptions.json"
    assumptions_path.write_text(json.dumps((assumptions or cost.CostAssumptions()).as_dict(), indent=2),
                                encoding="utf-8")

    runs_path = out_dir / "selected_runs.json"
    runs_path.write_text(json.dumps([
        {
            "model": ref.model,
            "group": ref.group,
            "run_id": ref.run_id,
            "configs": ref.configs,
            "repetitions": ref.settings.get("repetitions"),
            "edit_mode": ref.settings.get("edit_mode"),
            "started": ref.settings.get("started"),
        }
        for ref in selected
    ], indent=2), encoding="utf-8")
    return [summary_path, groups_path, costs_path, radar_path, assumptions_path, runs_path]


def print_costs(costs: pd.DataFrame) -> None:
    print(f"\n{'Cost (EUR)':<35}  {'per repetition':<28} {'per passing trial':<19} whole run")
    for row in costs.itertuples(index=False):
        per_rep = cost.format_eur(row.cost_per_rep_eur)
        if row.cost_per_rep_eur_high > row.cost_per_rep_eur_low:
            per_rep += f" ({cost.format_eur(row.cost_per_rep_eur_low)}-{cost.format_eur(row.cost_per_rep_eur_high)})"
        print(
            f"  {row.model:<22} {row.suite:<9}  {per_rep:<28} {cost.format_eur(row.cost_per_pass_eur):<19} "
            f"{cost.format_eur(row.total_cost_eur)}  [{row.cost_basis}]"
        )


def main() -> None:
    args = parse_args()
    try:
        overrides = agg.parse_group_overrides(args.group)
        radar_weights = stats.parse_radar_weights(args.radar_weight)
    except ValueError as e:
        raise SystemExit(str(e))

    results_dir = args.results_dir or RESULTS_DIR
    if not results_dir.is_dir():
        raise SystemExit(f"No such results directory: {results_dir}")
    refs = agg.all_run_refs(results_dir, overrides=overrides)
    selected = agg.latest_full_runs(refs, args.models)

    if args.list:
        print_listing(refs, selected, results_dir)
        return

    if args.verbose:
        for ref in refs:
            if not ref.full:
                print(f"skipping {ref.run_id} ({ref.model}): {ref.reason}")

    if args.models:
        missing = sorted({m.lower() for m in args.models} - {r.model.lower() for r in selected})
        if missing:
            print(f"warning: no full reproducibility run for: {', '.join(missing)} (see --list)", file=sys.stderr)
    if not selected:
        raise SystemExit("No full reproducibility runs to compare (see --list).")

    for warning in agg.comparability_warnings(selected):
        print(f"warning: {warning}", file=sys.stderr)

    print("Comparing:")
    for ref in selected:
        print(f"  {ref.model:<28} {ref.group:<12} run {ref.run_id}")

    out_dir = args.out or results_dir / "comparisons" / datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    assumptions = cost.assumptions_from_args(args)
    frames = build_frames(selected, assumptions, radar_weights=radar_weights)
    unpriced = sorted(set(frames["costs"].loc[frames["costs"]["cost_basis"].str.contains(cost.UNPRICED), "model"]))
    if unpriced:
        print(f"warning: no price known for {', '.join(unpriced)} - an API model needs adding to "
              "analysis/costs.py; a cluster run needs --gpu-hour-price \"<GPU name>=<EUR>\" for its GPU "
              "(the name is in the run's settings.hardware.gpus)", file=sys.stderr)
    print_costs(frames["costs"])

    written = plot_comparison(frames, out_dir, args.format, args.dpi, assumptions, radar_weights)
    written += write_tables(frames, selected, out_dir, assumptions)
    for path in written:
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
