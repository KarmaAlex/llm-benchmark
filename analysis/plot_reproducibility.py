"""
Render one reproducibility run (runner/run_all_reproducibility.py) as figures.

Reads the run's reproducibility.json and every rep-NN/report.json and writes,
under results/<run>/plots/ by default:

    classification      share of cases identical / equivalent / outcome-stable / flaky
    pass_matrix         cases x repetitions, pass / fail / harness error
    repetition_rate     each repetition's pass rate with mean and +/-1 sd
    case_stability      per-case agreement rate and number of distinct outputs
    sonar_funnel        how far sonar trials got through the pipeline, per case
    latency_tokens      per-case latency and completion-token spread
    markdown_difficulty markdown pass rate by difficulty
    cost_by_case        what one attempt at each case costs (API fees, or
                        electricity for local models - see analysis/costs.py)
    costs.csv           per-suite token, energy and cost totals

Partial runs (a subset of cases, one suite, interrupted) still plot whatever
they contain; the script says what makes the run incomplete.

Usage:
    python -m analysis.plot_reproducibility                        # newest reproducibility run
    python -m analysis.plot_reproducibility 2026-09-27_13-49-37
    python -m analysis.plot_reproducibility <run> --format pdf --out figures/
"""

import argparse
from pathlib import Path

from analysis import aggregate as agg
from analysis import costs as cost
from analysis import statistics as stats
from runner.filesystem.results_manager import ResultsManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot one reproducibility run.")
    parser.add_argument("run_id", nargs="?", help="Run directory or its name under results/ (default: newest).")
    parser.add_argument("--out", type=Path, help="Output directory (default: results/<run>/plots/).")
    parser.add_argument("--format", choices=("png", "pdf", "svg"), default="png", help="Image format (default: png).")
    parser.add_argument("--dpi", type=int, default=200, help="Raster resolution (default: 200).")
    parser.add_argument(
        "--group",
        action="append",
        metavar="MODEL=commercial|open",
        help="Override the commercial/open-source group of a model (repeatable).",
    )
    cost.add_cost_arguments(parser)
    return parser.parse_args()


def resolve_run(run_id: str | None) -> Path:
    if run_id is None:
        runs = agg.reproducibility_runs()
        if not runs:
            raise SystemExit("No reproducibility runs (directories with a reproducibility.json) under results/.")
        return runs[0]
    try:
        path = ResultsManager.resolve_run_directory(run_id)
    except FileNotFoundError as e:
        raise SystemExit(str(e))
    if not (path / agg.AGGREGATE_FILE_NAME).exists():
        raise SystemExit(f"{path} has no {agg.AGGREGATE_FILE_NAME} - is it a reproducibility run?")
    return path


def plot_run(ref: agg.RunRef, out_dir: Path, fmt: str = "png", dpi: int = 200,
             assumptions: cost.CostAssumptions | None = None) -> list[Path]:
    # Imported here so the data layer stays usable without a plotting backend.
    from analysis import plots

    cases = agg.case_frame(ref)
    if cases.empty:
        raise SystemExit(f"{ref.run_id}: no aggregated suites to plot (still pending validation?)")
    reps = agg.rep_frame(ref)
    suites = agg.suite_frame(ref)
    rates = agg.repetition_rates(ref)
    title = f"{ref.model} ({ref.group.lower()})  ·  run {ref.run_id}"

    figures = {
        "classification": plots.classification_breakdown(cases, f"Reproducibility classes  ·  {title}"),
        "repetition_rate": plots.repetition_pass_rate(rates, suites, f"Pass rate per repetition  ·  {title}"),
        "case_stability": plots.case_stability(cases, f"Output agreement per case  ·  {title}"),
    }
    if not reps.empty:
        figures["pass_matrix"] = plots.pass_matrix(reps, f"Pass / fail per repetition  ·  {title}")
        figures["latency_tokens"] = plots.latency_tokens(reps, f"Latency and tokens across repetitions  ·  {title}")
    stages = agg.stage_frame(ref)
    if not stages.empty:
        figures["sonar_funnel"] = plots.sonar_stage_funnel(
            stages, stats.funnel_rates(stages), f"Sonar pipeline  ·  {title}"
        )
    difficulty = plots.markdown_by_difficulty(cases, f"Markdown pass rate  ·  {title}")
    if difficulty is not None:
        figures["markdown_difficulty"] = difficulty

    assumptions = assumptions or cost.CostAssumptions()
    trials = cost.trial_costs(ref, assumptions)
    written = []
    if not trials.empty:
        note = assumptions.note(set(trials["cost_basis"]))
        by_case = plots.cost_by_case(trials, f"Cost per case  ·  {title}", note)
        if by_case is not None:
            figures["cost_by_case"] = by_case
        written.append(write_costs(cost.cost_summary(trials, suites), out_dir))

    return [plots.save(fig, out_dir, name, fmt, dpi) for name, fig in figures.items()] + written


def write_costs(costs, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "costs.csv"
    costs.to_csv(path, index=False, float_format="%.6g")
    return path


def print_costs(ref: agg.RunRef, assumptions: cost.CostAssumptions) -> None:
    trials = cost.trial_costs(ref, assumptions)
    if trials.empty:
        return
    summary = cost.cost_summary(trials, agg.suite_frame(ref))
    for row in summary.itertuples(index=False):
        band = ""
        if row.cost_per_rep_eur_high > row.cost_per_rep_eur_low:
            band = f" ({cost.format_eur(row.cost_per_rep_eur_low)}-{cost.format_eur(row.cost_per_rep_eur_high)})"
        print(
            f"  {row.suite}: {cost.format_eur(row.cost_per_rep_eur)}{band} per repetition, "
            f"{cost.format_eur(row.cost_per_pass_eur)} per passing trial, "
            f"{cost.format_eur(row.total_cost_eur)} for the whole run [{row.cost_basis}]"
        )


def main() -> None:
    args = parse_args()
    try:
        overrides = agg.parse_group_overrides(args.group)
    except ValueError as e:
        raise SystemExit(str(e))

    ref = agg.load_run_ref(resolve_run(args.run_id), overrides=overrides)
    print(f"Run {ref.run_id}: {ref.model} ({ref.group})")
    if not ref.full:
        print(f"  note: not a full reproducibility run - {ref.reason}")

    assumptions = cost.assumptions_from_args(args)
    print_costs(ref, assumptions)

    out_dir = args.out or ref.path / "plots"
    for path in plot_run(ref, out_dir, args.format, args.dpi, assumptions):
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
