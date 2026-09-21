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
import json
import time
from dataclasses import asdict
from pathlib import Path

from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.filesystem.results_manager import ResultsManager
from runner.models.model_config import ModelConfig
from runner.providers.factory import ProviderFactory
from runner.run_all_sonar import (
    SonarCaseResult,
    discover_cases,
    generate_case,
)
from runner.sonar_tests.edit_pipeline import PROMPT_NAME_BY_EDIT_MODE
from runner.stats import tokens_per_second


def compute_generation_summary(results: list[SonarCaseResult], wall_time: float) -> dict:
    total = len(results)
    applied_count = sum(1 for r in results if r.applied)
    total_prompt_tokens = sum(r.prompt_tokens for r in results)
    total_completion_tokens = sum(r.completion_tokens for r in results)
    total_execution_time = sum(r.execution_time for r in results)

    return {
        "total_cases": total,
        "applied_count": applied_count,
        "applied_rate": applied_count / total if total else 0.0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "avg_tokens_per_second": tokens_per_second(total_completion_tokens, total_execution_time),
        "avg_execution_time": total_execution_time / total if total else 0.0,
        "total_execution_time": total_execution_time,
        "wall_time": wall_time,
    }


def print_generation_report(results: list[SonarCaseResult], summary: dict, run_id: str) -> None:
    print(
        f"\n{'Case':<10} {'Applied':<9} {'Time (s)':<10} "
        f"{'Tokens':<9} {'Tok/s':<8} {'Match':<16} Error"
    )
    for r in results:
        print(
            f"{r.case_id:<10} {str(r.applied):<9} "
            f"{r.execution_time:<10.2f} {r.total_tokens:<9} "
            f"{r.tokens_per_second:<8.1f} {r.edit_match_summary or '':<16} {r.error or ''}"
        )

    print(f"\nApplied:  {summary['applied_count']}/{summary['total_cases']} "
          f"({summary['applied_rate']:.0%})")
    print(f"Tokens:   {summary['total_prompt_tokens']} prompt + "
          f"{summary['total_completion_tokens']} completion = "
          f"{summary['total_tokens']} total")
    print(f"Throughput: {summary['avg_tokens_per_second']:.1f} completion tok/s (avg)")
    print(f"Avg model latency: {summary['avg_execution_time']:.2f}s per case")
    print(f"Total model time: {summary['total_execution_time']:.2f}s")
    print(f"Wall-clock run time: {summary['wall_time']:.2f}s")
    print(
        "\nNot validated yet - run `python -m runner.validate_sonar_run "
        f"{run_id}` to compile and test these cases."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run every sonar benchmark case's generation phase (model call + "
            "patch application) without compiling or running tests."
        )
    )
    parser.add_argument(
        "--config",
        default="qwen2.5-coder-7b-q4",
        help="Model config name under configs/ to use (default: qwen2.5-coder-7b-q4).",
    )
    parser.add_argument(
        "--edit-mode",
        choices=["diff", "structured", "toolcall"],
        default="diff",
        help="How the model expresses its fix (see main_sonar.py for details).",
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        default="cuda",
        help="Run local (llama.cpp) models on the GPU (default) or force CPU-only.",
    )
    args = parser.parse_args()

    config: ModelConfig = ConfigLoader.load(args.config)
    config = ConfigLoader.apply_device(config, args.device)

    if args.edit_mode == "toolcall" and not config.supports_tools:
        print(
            f"Model config '{config.name}' does not have supports_tools "
            "enabled. Use --edit-mode structured for this model instead."
        )
        raise SystemExit(1)

    prompt = PromptLoader.load(PROMPT_NAME_BY_EDIT_MODE[args.edit_mode])
    provider = ProviderFactory.create(config)

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    run_start = time.perf_counter()

    results: list[SonarCaseResult] = []
    for case_id in discover_cases():
        print(f"Generating {case_id}...")
        try:
            result = generate_case(case_id, args.edit_mode, provider, prompt, run_directory)
        except Exception as e:
            result = SonarCaseResult(
                case_id=case_id,
                edit_mode=args.edit_mode,
                applied=False,
                compiled=False,
                execution_time=0.0,
                compile_time=0.0,
                error=f"{type(e).__name__}: {e}",
            )
        results.append(result)

    wall_time = time.perf_counter() - run_start

    summary = compute_generation_summary(results, wall_time)
    print_generation_report(results, summary, run_directory.name)

    report_path = run_directory / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "config": config.name,
                "edit_mode": args.edit_mode,
                "validated": False,
                "summary": summary,
                "cases": [asdict(r) for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nGeneration-only report written to {report_path}")
    print(f"Run id: {run_directory.name}")


if __name__ == "__main__":
    main()
