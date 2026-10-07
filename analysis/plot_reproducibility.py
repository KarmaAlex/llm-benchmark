"""
Render one reproducibility run (runner/run_all_reproducibility.py) as figures.

Reads the run's reproducibility.json and every rep-NN/report.json and writes,
under results/<run>/plots/ by default, one figure per suite (<name>_markdown,
<name>_sonar) so each reads on its own in a document:

    pass_matrix_<suite>      cases x repetitions, pass / fail / harness error
    repetition_rate_<suite>  each repetition's pass rate with mean and +/-1 sd
    case_stability_<suite>   per-case agreement rate and number of distinct outputs
    latency_tokens_<suite>   per-case latency and completion-token spread
    cost_by_case_<suite>     what one attempt at each case costs (API fees, rented
                             GPU time or electricity - see analysis/costs.py)
    sonar_funnel             how far sonar trials got through the pipeline, per case
    costs.csv                per-suite token, energy and cost totals
    captions.md              with --captions: each figure's title and footnote,
                             left out of the images, for LaTeX captions

Partial runs (a subset of cases, one suite, interrupted) still plot whatever
they contain; the script says what makes the run incomplete.

Usage:
    python -m analysis.plot_reproducibility                        # newest reproducibility run
    python -m analysis.plot_reproducibility 2026-09-27_13-49-37
    python -m analysis.plot_reproducibility <run> --captions --out figures/
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
    parser.add_argument("--format", choices=("pdf", "png", "svg"), default="pdf",
                        help="Image format (default: pdf, which pdflatex can include).")
    parser.add_argument("--dpi", type=int, default=200, help="Raster resolution, for png (default: 200).")
    parser.add_argument("--captions", action="store_true",
                        help="Leave figure titles and footnotes out of the images and write them to captions.md "
                             "instead, to use as LaTeX captions.")
    parser.add_argument(
        "--group",
        action="append",
        metavar="MODEL=commercial|open",
        help="Override the commercial/open-source group of a model (repeatable).",
    )
    parser.add_argument("--cost-only", action="store_true",
                        help="Draw only cost_by_case (and costs.csv), e.g. to compare pricing assumptions "
                             "in a separate --out folder.")
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


def plot_run(ref: agg.RunRef, out_dir: Path, fmt: str = "pdf", dpi: int = 200,
             assumptions: cost.CostAssumptions | None = None, cost_only: bool = False,
             captions: bool = False) -> list[Path]:
    """Draw a run's figures; with `cost_only`, just cost_by_case and
    costs.csv - e.g. to redraw them under other pricing assumptions. With
    `captions`, titles and footnotes go to captions.md instead of into the
    images."""
    # Imported here so the data layer stays usable without a plotting backend.
    from analysis import plots

    plots.configure(captions=captions)

    cases = agg.case_frame(ref)
    if cases.empty:
        raise SystemExit(f"{ref.run_id}: no aggregated suites to plot (still pending validation?)")
    reps = agg.rep_frame(ref)
    suites = agg.suite_frame(ref)
    rates = agg.repetition_rates(ref)
    # Model and run on separate lines: run ids end in the model name, so one
    # line of both can be wider than a one-suite figure.
    title = f"{ref.model} ({plots.GROUP_LABELS.get(ref.group, ref.group).lower()})\nesecuzione {ref.run_id}"

    assumptions = assumptions or cost.CostAssumptions()
    trials = cost.trial_costs(ref, assumptions)

    # One figure per suite: a markdown and a sonar panel side by side are hard
    # to read at page width.
    figures = {}
    for suite in ("markdown", "sonar"):
        if suite not in set(cases["suite"]):
            continue
        suite_label = plots.SUITE_LABELS.get(suite, suite)
        suite_trials = only(trials, suite)
        if not suite_trials.empty:
            by_case = plots.cost_by_case(suite_trials, figure_title("Costo per caso", suite_label, title),
                                         assumptions.note(set(suite_trials["cost_basis"]),
                                                          set(suite_trials["measured_gpu"].dropna())))
            if by_case is not None:
                figures[f"cost_by_case_{suite}"] = by_case
        if cost_only:
            continue
        figures[f"repetition_rate_{suite}"] = plots.repetition_pass_rate(
            only(rates, suite), only(suites, suite), figure_title("Tasso di successo per ripetizione", suite_label, title))
        figures[f"case_stability_{suite}"] = plots.case_stability(
            only(cases, suite), figure_title("Concordanza degli output per caso", suite_label, title))
        suite_reps = only(reps, suite)
        if not suite_reps.empty:
            figures[f"pass_matrix_{suite}"] = plots.pass_matrix(suite_reps, figure_title("Superato / fallito per ripetizione", suite_label, title))
            figures[f"latency_tokens_{suite}"] = plots.latency_tokens(
                suite_reps, figure_title("Latenza e token nelle ripetizioni", suite_label, title))

    stages = agg.stage_frame(ref)
    if not stages.empty and not cost_only:
        figures["sonar_funnel"] = plots.sonar_stage_funnel(
            stages, stats.funnel_rates(stages), f"Pipeline Sonar\n{title}"
        )

    written = []
    if not trials.empty:
        written.append(write_costs(cost.cost_summary(trials, suites), out_dir))
    if captions:
        written.append(plots.save_captions(figures, out_dir, fmt))

    return [plots.save(fig, out_dir, name, fmt, dpi) for name, fig in figures.items()] + written


def figure_title(what: str, suite_label: str, title: str) -> str:
    """Figure and suite on the first line, then `title` (model, run) below,
    so the title is never wider than a one-suite figure."""
    return f"{what}  ·  {suite_label}\n{title}"


def only(frame, suite: str):
    """The rows of one suite (an empty frame stays empty)."""
    return frame[frame["suite"] == suite] if not frame.empty else frame


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
    for path in plot_run(ref, out_dir, args.format, args.dpi, assumptions, args.cost_only, args.captions):
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
