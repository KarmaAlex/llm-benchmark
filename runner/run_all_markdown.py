"""
Run every markdown-extraction benchmark case under benchmark/markdown/
against a single model and report the results.

Usage:
    python -m runner.run_all_markdown --config llama-3.1-8B-instruct-q6
"""

import argparse
import time
from dataclasses import asdict

from runner.cli.arguments import add_config_argument, add_device_argument
from runner.cli.loading import load_model_config
from runner.core.batch import run_cases
from runner.filesystem.results_manager import ResultsManager
from runner.markdown_tests.pipeline import discover_cases, failed_result, load_prompt, run_case
from runner.markdown_tests.report import compute_summary, print_report
from runner.providers.factory import ProviderFactory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every markdown benchmark case against a model and report the results."
    )
    add_config_argument(parser, default="llama-3.1-8B-instruct-q6")
    add_device_argument(parser)
    args = parser.parse_args()

    config = load_model_config(args.config, args.device)
    provider = ProviderFactory.create(config)
    prompt = load_prompt()

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    run_start = time.perf_counter()

    results = run_cases(
        discover_cases(),
        lambda case_id: run_case(case_id, provider, prompt),
        failed_result,
    )

    wall_time = time.perf_counter() - run_start

    summary = compute_summary(results, wall_time)
    print_report(results, summary)

    report_path = ResultsManager.write_report(
        run_directory,
        {
            "config": config.name,
            "summary": summary,
            "cases": [asdict(r) for r in results],
        },
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
