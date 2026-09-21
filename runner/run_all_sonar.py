"""
Run every SonarQube issue-resolution benchmark case under benchmark/sonar/
against a single model and report the results.

Usage:
    python -m runner.run_all_sonar --config qwen2.5-coder-7b-q4 --edit-mode diff
"""

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.paths import BENCHMARK_DIR
from runner.filesystem.prompt_loader import PromptLoader
from runner.filesystem.results_manager import ResultsManager
from runner.models.model_config import ModelConfig
from runner.models.model_response import ModelResponse
from runner.prompt_builder import PromptBuilder
from runner.providers.base import ModelProvider
from runner.providers.factory import ProviderFactory
from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.edit_pipeline import PROMPT_NAME_BY_EDIT_MODE, apply_model_response
from runner.sonar_tests.workspace import Workspace
from runner.stats import tokens_per_second
from runner.structured_edit import EDIT_FILE_TOOL_SCHEMA


@dataclass
class SonarCaseResult:
    case_id: str
    edit_mode: str
    applied: bool
    compiled: bool
    execution_time: float
    compile_time: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    finish_reason: str | None = None
    edit_match_summary: str | None = None
    error: str | None = None
    response_text: str | None = None
    diff: str | None = None


def discover_cases() -> list[str]:
    sonar_dir = BENCHMARK_DIR / "sonar"
    return sorted(
        p.name for p in sonar_dir.iterdir()
        if p.is_dir() and (p / "metadata.json").exists()
    )


def _edit_match_summary(edit_results) -> str | None:
    if not edit_results:
        return None
    counts = Counter(r.match_kind for r in edit_results if r.applied)
    if not counts:
        return None
    return ", ".join(f"{count} {kind}" for kind, count in sorted(counts.items()))


def run_case(
    case_id: str,
    edit_mode: str,
    provider: ModelProvider,
    prompt,
    run_directory: Path,
) -> SonarCaseResult:
    case = BenchmarkLoader.load(Path("sonar") / case_id)
    chat_prompt = PromptBuilder.build(prompt, case)

    if edit_mode == "toolcall":
        chat_prompt = replace(chat_prompt, tools=[EDIT_FILE_TOOL_SCHEMA])

    response: ModelResponse = provider.generate(chat_prompt)

    case_directory = run_directory / case_id
    case_directory.mkdir(parents=True, exist_ok=True)
    (case_directory / "response.txt").write_text(response.content, encoding="utf-8")

    project_directory = Workspace.create(
        case.project_path,
        case_directory / "project",
    )

    outcome = apply_model_response(edit_mode, project_directory, response)
    (case_directory / "patch.diff").write_text(outcome.diff or "", encoding="utf-8")

    token_stats = dict(
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.prompt_tokens + response.completion_tokens,
        tokens_per_second=tokens_per_second(response.completion_tokens, response.latency),
        finish_reason=response.finish_reason,
        edit_match_summary=_edit_match_summary(outcome.edit_results),
    )

    if not outcome.applied:
        return SonarCaseResult(
            case_id=case_id,
            edit_mode=edit_mode,
            applied=False,
            compiled=False,
            execution_time=response.latency,
            compile_time=0.0,
            error=outcome.error,
            response_text=response.content,
            diff=outcome.diff,
            **token_stats,
        )

    compilation = Compiler.compile(project_directory)

    return SonarCaseResult(
        case_id=case_id,
        edit_mode=edit_mode,
        applied=True,
        compiled=compilation.compiled,
        execution_time=response.latency,
        compile_time=compilation.execution_time,
        error=None if compilation.compiled else compilation.stderr,
        response_text=response.content,
        diff=outcome.diff,
        **token_stats,
    )


def compute_summary(results: list[SonarCaseResult], wall_time: float) -> dict:
    total = len(results)
    applied_count = sum(1 for r in results if r.applied)
    compiled_count = sum(1 for r in results if r.compiled)
    total_prompt_tokens = sum(r.prompt_tokens for r in results)
    total_completion_tokens = sum(r.completion_tokens for r in results)
    total_execution_time = sum(r.execution_time for r in results)
    total_compile_time = sum(r.compile_time for r in results)

    return {
        "total_cases": total,
        "applied_count": applied_count,
        "applied_rate": applied_count / total if total else 0.0,
        "compiled_count": compiled_count,
        "compiled_rate": compiled_count / total if total else 0.0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "avg_tokens_per_second": tokens_per_second(total_completion_tokens, total_execution_time),
        "avg_execution_time": total_execution_time / total if total else 0.0,
        "total_execution_time": total_execution_time,
        "total_compile_time": total_compile_time,
        "wall_time": wall_time,
    }


def print_report(results: list[SonarCaseResult], summary: dict) -> None:
    print(
        f"\n{'Case':<10} {'Applied':<9} {'Compiled':<10} {'Time (s)':<10} "
        f"{'Tokens':<9} {'Tok/s':<8} {'Match':<16} Error"
    )
    for r in results:
        print(
            f"{r.case_id:<10} {str(r.applied):<9} {str(r.compiled):<10} "
            f"{r.execution_time:<10.2f} {r.total_tokens:<9} "
            f"{r.tokens_per_second:<8.1f} {r.edit_match_summary or '':<16} {r.error or ''}"
        )

    print(f"\nApplied:  {summary['applied_count']}/{summary['total_cases']} "
          f"({summary['applied_rate']:.0%})")
    print(f"Compiled: {summary['compiled_count']}/{summary['total_cases']} "
          f"({summary['compiled_rate']:.0%})")
    print(f"Tokens:   {summary['total_prompt_tokens']} prompt + "
          f"{summary['total_completion_tokens']} completion = "
          f"{summary['total_tokens']} total")
    print(f"Throughput: {summary['avg_tokens_per_second']:.1f} completion tok/s (avg)")
    print(f"Avg model latency: {summary['avg_execution_time']:.2f}s per case")
    print(f"Total model time: {summary['total_execution_time']:.2f}s, "
          f"total compile time: {summary['total_compile_time']:.2f}s")
    print(f"Wall-clock run time: {summary['wall_time']:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every sonar benchmark case against a model and report the results."
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
        print(f"Running {case_id}...")
        try:
            result = run_case(case_id, args.edit_mode, provider, prompt, run_directory)
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

    summary = compute_summary(results, wall_time)
    print_report(results, summary)

    report_path = run_directory / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "config": config.name,
                "edit_mode": args.edit_mode,
                "summary": summary,
                "cases": [asdict(r) for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
