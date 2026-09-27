"""
Run every SonarQube issue-resolution benchmark case under benchmark/sonar/
against a single model and report the results.

Usage:
    python -m runner.run_all_sonar --config qwen2.5-coder-7b-q4 --edit-mode diff
"""

import argparse

from runner.cli.arguments import (
    add_cases_argument,
    add_config_argument,
    add_device_argument,
    add_edit_mode_argument,
    add_sonar_argument,
)
from runner.cli.loading import load_model_config
from runner.filesystem.results_manager import ResultsManager
from runner.providers.factory import ProviderFactory
from runner.sonar_tests.pipeline import load_prompt, run_suite
from runner.sonar_tests.report import compute_summary, print_report, report_payload


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
    add_cases_argument(parser)
    args = parser.parse_args()

    config = load_model_config(args.config, args.device, args.edit_mode)
    prompt = load_prompt(args.edit_mode)
    provider = ProviderFactory.create(config)

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    results, wall_time = run_suite(
        args.edit_mode, provider, prompt, run_directory, args.cases, args.sonar
    )

    summary = compute_summary(results, wall_time)
    print_report(results, summary)

    report_path = ResultsManager.write_report(
        run_directory,
        report_payload(config.name, args.edit_mode, args.sonar, results, summary),
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
