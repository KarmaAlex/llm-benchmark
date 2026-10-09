"""
Compare commercial and open-source models on their latest full
reproducibility runs.

For every model (a config name without its "(markdown)"/"(sonar)" suffix;
quantizations are separate models) the newest *full* run is selected: both
suites, every case, every repetition completed, sonar graded on clean fixes
(see analysis/aggregate.py:is_full_run). A model's group comes from the
provider in its configs/*.yaml - openai is commercial, llama.cpp is open
source - and can be overridden with --group.

Writes, under <results dir>/comparisons/<utc timestamp>/ by default, one
figure per suite (<name>_markdown, <name>_sonar) so each reads on its own in
a document:

    pass_rate_<suite>       pooled pass rate per model with 95% Wilson CI
    classification_<suite>  reproducibility classes per model
    case_heatmap_<suite>    per-case pass rate, models x cases
    efficiency_<suite>      pass rate vs the cost of one suite repetition, with
                            the Pareto frontier
    latency_<suite>         pass rate vs mean latency per case
    size_<suite>            pass rate vs reported parameter count (open source)
    cost_<suite>            cost of one suite repetition and of one passing trial
    radar_<suite>           one radar per model - accuracy, consistency (same
                            pass/fail outcome), speed, low cost - for comparing
                            models, with no combined score
    scorecard_<suite>       the radar's values as a table
    sonar_funnel            share of sonar trials reaching each pipeline stage
    captions.md             with --captions: each figure's title and footnote,
                            left out of the images, for LaTeX captions
    summary.csv             the numbers behind the figures, per model x suite
    radar_scores.csv        the raw measures and 0-1 scores behind the radars
    costs.csv               token, energy and cost totals, per model x suite
    cost_assumptions.json   prices, exchange rate and power draw used, with sources
    selected_runs.json      which run each model's numbers came from

Costs are in euros: OpenAI list prices for API models, GPU-hours for runs on a
rented GPU, electricity for local ones. See analysis/costs.py for the prices
and how to override them.

Usage:
    python -m analysis.compare_models --list        # every run, and which get selected
    python -m analysis.compare_models
    python -m analysis.compare_models --models GPT-5 Gemma-4-E4B-Q4-UD --format png
    python -m analysis.compare_models --captions      # titles/footnotes to captions.md, for LaTeX
    python -m analysis.compare_models --results-dir results/<folder>   # runs kept in a subfolder
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import aggregate as agg
from analysis import costs as cost
from analysis import italian
from analysis import statistics as stats
from analysis.model_sizes import model_size
from runner.filesystem.paths import RESULTS_DIR


SUMMARY_COLUMNS = [
    "model", "group", "suite", "run_id", "criterion", "repetitions", "total_cases", "trials", "passes",
    "pass_rate", "pass_rate_ci_low", "pass_rate_ci_high", "rep_pass_rate_mean", "rep_pass_rate_stdev",
    "pass_all", "pass_any", "pass_none",
    "share_identical", "share_equivalent", "share_outcome-stable", "share_flaky", "share_harness-error",
    "share_stable_output", "mean_agreement_rate", "mean_outcome_agreement", "mean_distinct_outputs",
    "latency_mean", "latency_measured",
    "tokens_mean", "params_b", "effective_params_b", "cost_basis", "cost_per_rep_eur", "cost_per_pass_eur", "priced_gpu", "time_scale",
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
    parser.add_argument("--format", choices=("pdf", "png", "svg"), default="pdf",
                        help="Image format (default: pdf, which pdflatex can include).")
    parser.add_argument("--dpi", type=int, default=200, help="Raster resolution, for png (default: 200).")
    parser.add_argument("--captions", action="store_true",
                        help="Leave figure titles and footnotes out of the images and write them to captions.md "
                             "instead, to use as LaTeX captions.")
    parser.add_argument("--list", action="store_true", help="List reproducibility runs and the selection, then exit.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Explain why runs were skipped.")
    parser.add_argument("--cost-only", action="store_true",
                        help="Draw only the figures that depend on pricing or GPU assumptions (efficiency, "
                             "cost, latency, radar, scorecard), e.g. to compare assumptions in a separate --out "
                             "folder.")
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
                 providers: dict[str, str] | None = None,
                 model_ids: dict[str, str] | None = None) -> dict[str, pd.DataFrame]:
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
        costs[["model", "suite", "cost_basis", "cost_per_rep_eur", "cost_per_pass_eur", "priced_gpu", "time_scale"]],
        on=["model", "suite"], how="left",
    )
    # Under --price-as-gpu a run's latency is estimated for the GPU it is
    # priced as, with the same scale as its cost, so latency, cost and the
    # radar all describe one deployment. The measured value is kept beside it.
    summary["latency_measured"] = summary["latency_mean"]
    summary["latency_mean"] = summary["latency_mean"] * summary["time_scale"].fillna(1.0)
    sizes = {model: model_size(model) for model in summary["model"]}
    summary["params_b"] = summary["model"].map(lambda m: sizes[m].params_b if sizes[m] else None).astype(float)
    summary["effective_params_b"] = summary["model"].map(
        lambda m: sizes[m].effective_b if sizes[m] else None).astype(float)
    summary["size_note"] = summary["model"].map(lambda m: sizes[m].note if sizes[m] else "")
    return {
        "cases": cases,
        "summary": summary,
        "stages": stages,
        "funnel": stats.funnel_rates(stages),
        "costs": costs,
        "radar": stats.radar_scores(summary),
    }


def latency_note(costs: pd.DataFrame) -> str:
    """Footnote for latency figures: where each latency comes from, and any
    --price-as-gpu estimate."""
    parts = ["Latenza: tempo medio di chiamata al modello per caso, sull'hardware di ciascun modello (API "
             "OpenAI, GPU del cluster o portatile), quindi confronta configurazioni, non solo modelli"]
    estimated = costs[costs["time_scale"].fillna(1.0) > 1]
    for (measured, priced, scale), _rows in estimated.groupby(["measured_gpu", "priced_gpu", "time_scale"]):
        parts.append(f"GPU a noleggio (stima): tempo misurato su {measured} × {italian.number(scale, '.2f')} "
                     f"(banda di memoria) per {priced}")
    return "  ·  ".join(parts)


def only(frame: pd.DataFrame, suite: str) -> pd.DataFrame:
    """The rows of one suite."""
    return frame[frame["suite"] == suite]


SIZE_NOTE = ("Parametri: il totale dichiarato nella scheda di ciascun modello (B = miliardi). Se un modello "
             "ne usa meno nel calcolo, l'etichetta riporta il numero effettivo (serie E di Gemma) o attivo "
             "(mixture of experts). La quantizzazione (Q4, Q8, F16, nel nome) cambia la memoria richiesta, "
             "non il numero di parametri. I modelli commerciali non hanno una dimensione pubblicata e sono "
             "tracciati come linee al loro tasso di successo.")


def plot_comparison(frames: dict[str, pd.DataFrame], out_dir: Path, fmt: str = "pdf", dpi: int = 200,
                    assumptions: cost.CostAssumptions | None = None,
                    cost_only: bool = False,
                    captions: bool = False) -> list[Path]:
    """Draw the comparison figures; with `cost_only`, just the ones that
    depend on pricing or GPU assumptions (efficiency, cost, latency, radar,
    scorecard) - e.g. to redraw them under other assumptions next to an
    existing set. With `captions`, titles and footnotes go to captions.md
    instead of into the images."""
    from analysis import plots

    assumptions = assumptions or cost.CostAssumptions()
    plots.configure(captions=captions)

    cases, summary, costs = frames["cases"], frames["summary"], frames["costs"]
    # One figure per suite: a markdown and a sonar panel side by side are hard
    # to read at page width.
    figures = {}
    for suite in ("markdown", "sonar"):
        if suite not in set(summary["suite"]):
            continue
        label = plots.SUITE_LABELS.get(suite, suite)
        suite_summary, suite_cases, suite_costs = only(summary, suite), only(cases, suite), only(costs, suite)
        if not cost_only:
            figures[f"pass_rate_{suite}"] = plots.pass_rate_comparison(suite_summary)
            figures[f"classification_{suite}"] = plots.classification_comparison(suite_cases)
            figures[f"case_heatmap_{suite}"] = plots.case_pass_heatmap(suite_cases)
            if suite_summary["params_b"].notna().any():
                figures[f"size_{suite}"] = plots.pass_rate_vs_size(
                    suite_summary, f"{label}: tasso di successo e dimensione del modello", note=SIZE_NOTE)
        figures[f"latency_{suite}"] = plots.pass_rate_scatter(
            suite_summary, "latency_mean", "latenza media per caso (s, scala log.)",
            f"{label}: tasso di successo e latenza", note=latency_note(suite_costs))
        if suite_costs["cost_per_rep_eur"].notna().any():
            note = assumptions.note({b for basis in suite_costs["cost_basis"] for b in basis.split("/")},
                                    set(suite_costs["measured_gpu"].dropna()))
            figures[f"efficiency_{suite}"] = plots.pass_rate_scatter(
                suite_summary, "cost_per_rep_eur", "costo di una ripetizione della suite (scala log.)",
                f"{label}: tasso di successo e costo", euro=True, note=note, frontier=True)
            figures[f"cost_{suite}"] = plots.cost_comparison(suite_costs, note)
    if not frames["funnel"].empty and not cost_only:
        figures["sonar_funnel"] = plots.sonar_funnel_comparison(frames["funnel"])
    scaled = costs[costs["time_scale"].fillna(1.0) > 1]
    speed_note = (
        "Velocità e costo dei modelli su GPU a noleggio sono stime per "
        + ", ".join(sorted(set(scaled["priced_gpu"].dropna())))
        + f" (tempo misurato × {italian.number(scaled['time_scale'].max(), '.2f')}, banda di memoria)."
    ) if not scaled.empty else None
    radar = frames["radar"]
    for suite in ("markdown", "sonar"):
        suite_scores = only(radar, suite) if not radar.empty else radar
        if not suite_scores.empty:
            figures[f"radar_{suite}"] = plots.radar_comparison(suite_scores, speed_note)
            figures[f"scorecard_{suite}"] = plots.scorecard(suite_scores, speed_note)
    written = []
    if captions:
        written.append(plots.save_captions(figures, out_dir, fmt))
    return [plots.save(fig, out_dir, name, fmt, dpi) for name, fig in figures.items()] + written


def write_tables(frames: dict[str, pd.DataFrame], selected: list[agg.RunRef], out_dir: Path,
                 assumptions: cost.CostAssumptions | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = frames["summary"]
    columns = [c for c in SUMMARY_COLUMNS if c in summary.columns]
    summary_path = out_dir / "summary.csv"
    summary[columns].to_csv(summary_path, index=False, float_format="%.4f")

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
    return [summary_path, costs_path, radar_path, assumptions_path, runs_path]


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
    frames = build_frames(selected, assumptions)
    unpriced = sorted(set(frames["costs"].loc[frames["costs"]["cost_basis"].str.contains(cost.UNPRICED), "model"]))
    if unpriced:
        print(f"warning: no price known for {', '.join(unpriced)} - an API model needs adding to "
              "analysis/costs.py; a cluster run needs --gpu-hour-price \"<GPU name>=<EUR>\" for its GPU "
              "(the name is in the run's settings.hardware.gpus)", file=sys.stderr)
    print_costs(frames["costs"])

    written = plot_comparison(frames, out_dir, args.format, args.dpi, assumptions, args.cost_only,
                              args.captions)
    written += write_tables(frames, selected, out_dir, assumptions)
    for path in written:
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
