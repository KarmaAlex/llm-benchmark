"""
Run every SonarQube issue-resolution benchmark case's generation phase only:
call the model and apply its patch to a fresh workspace, without compiling
or running tests. This is useful when you want to collect model responses
quickly (e.g. across several models) and defer the slower mvn compile/test
validation phase to later, or run it on a different machine.

Use `runner/validate_sonar_run.py <run_id>` afterwards to run that
validation phase against the run directory this script produces.

Usage:
    python -m runner.run_all_sonar_generate --config qwen2.5-coder-7b-q4 --edit-mode diff
"""

import argparse
import time
from dataclasses import asdict

from runner.cli.arguments import add_config_argument, add_device_argument, add_edit_mode_argument
from runner.cli.loading import load_model_config
from runner.core.batch import run_cases
from runner.filesystem.results_manager import ResultsManager
from runner.providers.factory import ProviderFactory
from runner.sonar_tests.pipeline import discover_cases, failed_result, generate_case, load_prompt
from runner.sonar_tests.report import compute_generation_summary, print_generation_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run every sonar benchmark case's generation phase (model call + "
            "patch application) without compiling or running tests."
        )
    )
    add_config_argument(parser, default="qwen2.5-coder-7b-q4")
    add_edit_mode_argument(parser)
    add_device_argument(parser)
    args = parser.parse_args()

    config = load_model_config(args.config, args.device, args.edit_mode)
    prompt = load_prompt(args.edit_mode)
    provider = ProviderFactory.create(config)

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    run_start = time.perf_counter()

    results = run_cases(
        discover_cases(),
        lambda case_id: generate_case(case_id, args.edit_mode, provider, prompt, run_directory),
        lambda case_id, error: failed_result(case_id, args.edit_mode, error),
        verb="Generating",
    )

    wall_time = time.perf_counter() - run_start

    summary = compute_generation_summary(results, wall_time)
    print_generation_report(results, summary, run_directory.name)

    report_path = ResultsManager.write_report(
        run_directory,
        {
            "config": config.name,
            "edit_mode": args.edit_mode,
            "validated": False,
            "summary": summary,
            "cases": [asdict(r) for r in results],
        },
    )
    print(f"\nGeneration-only report written to {report_path}")
    print(f"Run id: {run_directory.name}")


if __name__ == "__main__":
    main()
