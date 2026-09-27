"""
Run every markdown-extraction benchmark case under benchmark/markdown/
against a single model and report the results.

Usage:
    python -m runner.run_all_markdown --config llama-3.1-8B-instruct-q6
"""

import argparse

from runner.cli.arguments import add_cases_argument, add_config_argument, add_device_argument
from runner.cli.loading import load_model_config
from runner.filesystem.results_manager import ResultsManager
from runner.markdown_tests.pipeline import load_prompt, run_suite
from runner.markdown_tests.report import compute_summary, print_report, report_payload
from runner.providers.factory import ProviderFactory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every markdown benchmark case against a model and report the results."
    )
    add_config_argument(parser, default="llama-3.1-8B-instruct-q6")
    add_device_argument(parser)
    add_cases_argument(parser)
    args = parser.parse_args()

    config = load_model_config(args.config, args.device)
    provider = ProviderFactory.create(config)
    prompt = load_prompt()

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    results, wall_time = run_suite(provider, prompt, args.cases)

    summary = compute_summary(results, wall_time)
    print_report(results, summary)

    report_path = ResultsManager.write_report(
        run_directory,
        report_payload(config.name, results, summary),
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
