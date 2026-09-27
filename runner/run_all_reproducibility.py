"""
Run both benchmark suites several times with the same model and report how
reproducible each case is: whether the model's responses changed between
repetitions (and how), and how often each case passed.

Every repetition is a normal run, written to its own directory with the
same report.json the run_all_* scripts produce, so `analysis.report`,
`validate_sonar_run` and `analyze_sonar_run` all work on it unchanged:

    results/<timestamp>/
        reproducibility.json          settings + per-suite, per-case aggregate
        markdown/rep-01/report.json
        sonar/rep-01/report.json      (+ case workspaces and sonar-logs)
        ...

The aggregate is always rebuilt from those reports, so `--aggregate-only`
re-grades a finished (or interrupted) run without calling the model. See
runner/reproducibility/aggregate.py for the classification criteria.

With --no-sonar, sonar repetitions only generate (no mvn compile/test
either, matching run_all_sonar_generate.py's "validated": false convention):
run `validate_sonar_run` on each `sonar/rep-NN/` directory whenever
convenient, then `--aggregate-only` to grade the run on its tests.

Usage:
    python -m runner.run_all_reproducibility --model qwen2.5-coder-7b-q4
    python -m runner.run_all_reproducibility --model gpt5mini --repetitions 5 --suites markdown
    python -m runner.run_all_reproducibility --aggregate-only 2026-09-24_10-00-00
"""

import argparse
import gc
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from runner.cli.arguments import (
    add_cases_argument,
    add_device_argument,
    add_edit_mode_argument,
    add_sonar_argument,
)
from runner.cli.loading import load_model_config, resolve_config_name
from runner.core.batch import run_cases
from runner.filesystem.results_manager import ResultsManager
from runner.markdown_tests import pipeline as markdown_pipeline
from runner.markdown_tests import report as markdown_report
from runner.models.model_config import ModelConfig
from runner.providers.factory import ProviderFactory
from runner.reproducibility.aggregate import AGGREGATE_FILE_NAME, SUITES, aggregate_run
from runner.reproducibility.report import print_reproducibility_report
from runner.sonar_tests import pipeline as sonar_pipeline
from runner.sonar_tests import report as sonar_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the markdown and sonar suites repeatedly with one model and "
            "report per-case reproducibility and pass rates."
        )
    )
    parser.add_argument(
        "--model",
        help=(
            "Base model config name. Each suite uses <model>-markdown / "
            "<model>-sonar when that config exists, otherwise <model> itself."
        ),
    )
    parser.add_argument("--markdown-config", help="Explicit config for the markdown suite (overrides --model).")
    parser.add_argument("--sonar-config", help="Explicit config for the sonar suite (overrides --model).")
    parser.add_argument(
        "--repetitions",
        type=int,
        default=10,
        help="How many times to run each suite (default: 10).",
    )
    parser.add_argument(
        "--suites",
        nargs="+",
        choices=SUITES,
        default=list(SUITES),
        help="Which suites to run (default: both).",
    )
    add_edit_mode_argument(parser)
    add_device_argument(parser)
    add_sonar_argument(
        parser,
        help=(
            "Compile, test and run the SonarQube analysis phase on every "
            "sonar repetition, so 'pass' means a clean fix (default: on). "
            "With --no-sonar, repetitions only generate - no compile/test "
            "either - and are graded later by running validate_sonar_run "
            "on each repetition and re-aggregating with --aggregate-only."
        ),
    )
    add_cases_argument(parser)
    parser.add_argument(
        "--aggregate-only",
        metavar="RUN_ID",
        help=(
            "Don't run anything: rebuild reproducibility.json and the report "
            "from an existing run directory's completed repetitions."
        ),
    )
    args = parser.parse_args()

    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if not args.aggregate_only:
        for suite in args.suites:
            if not (args.model or getattr(args, f"{suite}_config")):
                parser.error(f"--model (or --{suite}-config) is required to run the {suite} suite")
    return args


def suite_config_name(args: argparse.Namespace, suite: str) -> str:
    return getattr(args, f"{suite}_config") or resolve_config_name(args.model, suite)


def cases_per_suite(args: argparse.Namespace) -> dict[str, list[str] | None]:
    """Split --cases between the suites they belong to. None means every
    case; a suite none of the requested cases belong to is skipped."""
    if not args.cases:
        return {suite: None for suite in args.suites}

    available = {
        "markdown": set(markdown_pipeline.discover_cases()),
        "sonar": set(sonar_pipeline.discover_cases()),
    }
    unknown = [c for c in args.cases if not any(c in ids for ids in available.values())]
    if unknown:
        raise SystemExit(f"Unknown case id(s): {', '.join(unknown)}")

    selected = {suite: [c for c in args.cases if c in available[suite]] for suite in args.suites}
    return {suite: ids for suite, ids in selected.items() if ids}


def run_markdown_repetitions(
    config: ModelConfig,
    suite_directory: Path,
    repetitions: int,
    case_ids: list[str] | None,
) -> None:
    provider = ProviderFactory.create(config)
    prompt = markdown_pipeline.load_prompt()

    for rep in range(1, repetitions + 1):
        rep_directory = repetition_directory(suite_directory, rep, repetitions, "markdown")
        results, wall_time = markdown_pipeline.run_suite(provider, prompt, case_ids)
        summary = markdown_report.compute_summary(results, wall_time)

        payload = markdown_report.report_payload(config.name, results, summary)
        ResultsManager.write_report(rep_directory, {**payload, "repetition": rep})
        print(
            f"markdown rep {rep}/{repetitions}: matched {summary['matched_count']}/"
            f"{summary['total_cases']} ({summary['matched_rate']:.0%}) in {wall_time:.1f}s"
        )


def run_sonar_repetitions(
    config: ModelConfig,
    suite_directory: Path,
    repetitions: int,
    case_ids: list[str] | None,
    edit_mode: str,
    sonar: bool,
) -> None:
    provider = ProviderFactory.create(config)
    prompt = sonar_pipeline.load_prompt(edit_mode)

    for rep in range(1, repetitions + 1):
        rep_directory = repetition_directory(suite_directory, rep, repetitions, "sonar")

        if sonar:
            results, wall_time = sonar_pipeline.run_suite(
                edit_mode, provider, prompt, rep_directory, case_ids, sonar
            )
            summary = sonar_report.compute_summary(results, wall_time)
            payload = sonar_report.report_payload(config.name, edit_mode, sonar, results, summary)
            outcome = f"clean fixes {summary['clean_fix_count']}/{summary['total_cases']}"
        else:
            # No SonarQube analysis requested, so there is no reason to pay
            # for mvn compile/test here either: generate only, and leave
            # that slower phase to validate_sonar_run on this rep directory
            # whenever it's convenient (a different machine, later, ...).
            results, wall_time = generate_sonar_repetition(
                provider, prompt, rep_directory, case_ids, edit_mode
            )
            summary = sonar_report.compute_generation_summary(results, wall_time)
            payload = {
                "config": config.name,
                "edit_mode": edit_mode,
                "sonar_analyzed": False,
                "validated": False,
                "summary": summary,
                "cases": [asdict(r) for r in results],
            }
            outcome = f"applied {summary['applied_count']}/{summary['total_cases']} (not yet validated)"

        ResultsManager.write_report(rep_directory, {**payload, "repetition": rep})
        print(f"sonar rep {rep}/{repetitions}: {outcome} in {wall_time:.1f}s")


def generate_sonar_repetition(provider, prompt, rep_directory: Path, case_ids, edit_mode: str):
    run_start = time.perf_counter()
    results = run_cases(
        case_ids or sonar_pipeline.discover_cases(),
        lambda case_id: sonar_pipeline.generate_case(case_id, edit_mode, provider, prompt, rep_directory),
        lambda case_id, error: sonar_pipeline.failed_result(case_id, edit_mode, error),
        verb="Generating",
    )
    return results, time.perf_counter() - run_start


def repetition_directory(suite_directory: Path, rep: int, repetitions: int, suite: str) -> Path:
    print(f"\n=== {suite} repetition {rep}/{repetitions} ===")
    directory = suite_directory / f"rep-{rep:02d}"
    directory.mkdir(parents=True)
    return directory


def run(args: argparse.Namespace) -> Path:
    selected_cases = cases_per_suite(args)
    # Load (and validate) every config before spending time on the first suite.
    configs = {
        suite: load_model_config(
            suite_config_name(args, suite),
            args.device,
            args.edit_mode if suite == "sonar" else None,
        )
        for suite in selected_cases
    }

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    settings = {
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repetitions": args.repetitions,
        "suites": list(selected_cases),
        "configs": {suite: config.name for suite, config in configs.items()},
        "edit_mode": args.edit_mode,
        "sonar": args.sonar,
        "device": args.device,
        "cases": args.cases,
    }
    # Written up front so --aggregate-only on an interrupted run still knows
    # what was asked for.
    ResultsManager.write_report(run_directory, {"settings": settings, "suites": {}}, AGGREGATE_FILE_NAME)

    for suite, case_ids in selected_cases.items():
        suite_directory = run_directory / suite
        if suite == "markdown":
            run_markdown_repetitions(configs[suite], suite_directory, args.repetitions, case_ids)
        else:
            run_sonar_repetitions(
                configs[suite], suite_directory, args.repetitions, case_ids, args.edit_mode, args.sonar
            )
        # Release this suite's model before the next one loads, so two local
        # models never sit on the GPU at the same time.
        gc.collect()

    return run_directory


def existing_settings(run_directory: Path) -> dict:
    try:
        return ResultsManager.load_report(run_directory, AGGREGATE_FILE_NAME).get("settings", {})
    except FileNotFoundError:
        return {}


def main() -> None:
    args = parse_args()

    if args.aggregate_only:
        try:
            run_directory = ResultsManager.resolve_run_directory(args.aggregate_only)
        except FileNotFoundError as e:
            raise SystemExit(str(e))
    else:
        run_directory = run(args)

    aggregate = aggregate_run(run_directory, existing_settings(run_directory))
    print_reproducibility_report(aggregate)

    aggregate_path = ResultsManager.write_report(run_directory, aggregate, AGGREGATE_FILE_NAME)
    print(f"\nReproducibility report written to {aggregate_path}")


if __name__ == "__main__":
    main()
