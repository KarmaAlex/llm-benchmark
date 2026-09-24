"""
Run every SonarQube issue-resolution benchmark case under benchmark/sonar/
against a single model and report the results.

Usage:
    python -m runner.run_all_sonar --config qwen2.5-coder-7b-q4 --edit-mode diff
"""

import argparse
import time
from dataclasses import asdict

from runner.cli.arguments import (
    add_config_argument,
    add_device_argument,
    add_edit_mode_argument,
    add_sonar_argument,
)
from runner.cli.loading import load_model_config
from runner.core.batch import run_cases
from runner.filesystem.results_manager import ResultsManager
from runner.providers.factory import ProviderFactory
from runner.sonar_tests.pipeline import (
    analyze_run,
    discover_cases,
    failed_result,
    load_prompt,
    run_case,
)
from runner.sonar_tests.report import compute_summary, print_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every sonar benchmark case against a model and report the results."
    )
    add_config_argument(parser, default="qwen2.5-coder-7b-q4")
    add_edit_mode_argument(parser)
    add_device_argument(parser)
    add_sonar_argument(
        parser,
        help=(
            "After compiling and testing, analyze every case with a real SonarQube "
            "to check the reported issue is gone and no new ones appeared "
            "(default: on). Uses the shared long-lived container; see "
            "scripts/sonar_server.py."
        ),
    )
    args = parser.parse_args()

    config = load_model_config(args.config, args.device, args.edit_mode)
    prompt = load_prompt(args.edit_mode)
    provider = ProviderFactory.create(config)

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    run_start = time.perf_counter()

    results = run_cases(
        discover_cases(),
        lambda case_id: run_case(case_id, args.edit_mode, provider, prompt, run_directory),
        lambda case_id, error: failed_result(case_id, args.edit_mode, error),
    )

    if args.sonar:
        print("\nRunning SonarQube analysis...")
        results = analyze_run(results, run_directory)

    wall_time = time.perf_counter() - run_start

    summary = compute_summary(results, wall_time)
    print_report(results, summary)

    report_path = ResultsManager.write_report(
        run_directory,
        {
            "config": config.name,
            "edit_mode": args.edit_mode,
            "sonar_analyzed": args.sonar,
            "summary": summary,
            "cases": [asdict(r) for r in results],
        },
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
