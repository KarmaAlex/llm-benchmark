"""
Run every markdown-extraction benchmark case under benchmark/markdown/
against a single model and report the results.

Usage:
    python -m runner.run_all_markdown --config llama-3.1-8B-instruct-q6
"""

import argparse
import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.paths import BENCHMARK_DIR
from runner.filesystem.prompt_loader import PromptLoader
from runner.filesystem.results_manager import ResultsManager
from runner.markdown_tests.json_comparator import JsonComparator
from runner.markdown_tests.json_extractor import JsonExtractionError, JsonExtractor
from runner.models.model_config import ModelConfig
from runner.prompt_builder import PromptBuilder
from runner.providers.base import ModelProvider
from runner.providers.factory import ProviderFactory
from runner.stats import tokens_per_second


@dataclass
class MarkdownCaseResult:
    case_id: str
    difficulty: int | None
    matched: bool
    execution_time: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    gpu_memory_mb: float | None = None
    finish_reason: str | None = None
    error: str | None = None
    response_text: str | None = None
    parsed_output: object = None


def discover_cases() -> list[str]:
    markdown_dir = BENCHMARK_DIR / "markdown"
    return sorted(
        p.name for p in markdown_dir.iterdir()
        if p.is_dir() and (p / "metadata.json").exists()
    )


def run_case(
    case_id: str,
    provider: ModelProvider,
    prompt,
    run_directory: Path,
) -> MarkdownCaseResult:
    case = BenchmarkLoader.load(Path("markdown") / case_id)
    chat_prompt = PromptBuilder.build(prompt, case)

    response = provider.generate(chat_prompt)

    difficulty = case.metadata.get("difficulty")
    token_stats = dict(
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.prompt_tokens + response.completion_tokens,
        tokens_per_second=tokens_per_second(response.completion_tokens, response.latency),
        gpu_memory_mb=response.gpu_memory_mb,
        finish_reason=response.finish_reason,
    )

    try:
        parsed = JsonExtractor.extract(response.content)
    except JsonExtractionError as e:
        return MarkdownCaseResult(
            case_id=case_id,
            difficulty=difficulty,
            matched=False,
            execution_time=response.latency,
            error=str(e),
            response_text=response.content,
            **token_stats,
        )

    comparison = JsonComparator.compare(parsed, case.resources["expected"])

    return MarkdownCaseResult(
        case_id=case_id,
        difficulty=difficulty,
        response_text=response.content,
        parsed_output=parsed,
        matched=comparison.matched,
        execution_time=response.latency,
        error=None if comparison.matched else comparison.message,
        **token_stats,
    )


def compute_summary(results: list[MarkdownCaseResult], wall_time: float) -> dict:
    total = len(results)
    matched_count = sum(1 for r in results if r.matched)
    total_prompt_tokens = sum(r.prompt_tokens for r in results)
    total_completion_tokens = sum(r.completion_tokens for r in results)
    total_execution_time = sum(r.execution_time for r in results)
    gpu_memory_samples = [r.gpu_memory_mb for r in results if r.gpu_memory_mb is not None]
    peak_gpu_memory_mb = max(gpu_memory_samples) if gpu_memory_samples else None

    by_difficulty: dict[int, dict] = defaultdict(lambda: {"total": 0, "matched": 0})
    for r in results:
        key = r.difficulty if r.difficulty is not None else -1
        by_difficulty[key]["total"] += 1
        if r.matched:
            by_difficulty[key]["matched"] += 1

    return {
        "total_cases": total,
        "matched_count": matched_count,
        "matched_rate": matched_count / total if total else 0.0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "avg_tokens_per_second": tokens_per_second(total_completion_tokens, total_execution_time),
        "avg_execution_time": total_execution_time / total if total else 0.0,
        "total_execution_time": total_execution_time,
        "peak_gpu_memory_mb": peak_gpu_memory_mb,
        "wall_time": wall_time,
        "by_difficulty": {
            str(k): v for k, v in sorted(by_difficulty.items())
        },
    }


def print_report(results: list[MarkdownCaseResult], summary: dict) -> None:
    print(
        f"\n{'Case':<10} {'Difficulty':<11} {'Matched':<9} {'Time (s)':<10} "
        f"{'Tokens':<9} {'Tok/s':<8} {'GPU MiB':<9} Error"
    )
    for r in results:
        error_summary = (r.error or "").splitlines()[0] if r.error else ""
        gpu_memory = f"{r.gpu_memory_mb:.0f}" if r.gpu_memory_mb is not None else "n/a"
        print(
            f"{r.case_id:<10} {str(r.difficulty):<11} {str(r.matched):<9} "
            f"{r.execution_time:<10.2f} {r.total_tokens:<9} "
            f"{r.tokens_per_second:<8.1f} {gpu_memory:<9} {error_summary}"
        )

    print(f"\nMatched: {summary['matched_count']}/{summary['total_cases']} "
          f"({summary['matched_rate']:.0%})")

    print("\nBy difficulty:")
    for difficulty, stats in summary["by_difficulty"].items():
        rate = stats["matched"] / stats["total"] if stats["total"] else 0.0
        print(f"  {difficulty}: {stats['matched']}/{stats['total']} ({rate:.0%})")

    print(f"\nTokens: {summary['total_prompt_tokens']} prompt + "
          f"{summary['total_completion_tokens']} completion = "
          f"{summary['total_tokens']} total")
    print(f"Throughput: {summary['avg_tokens_per_second']:.1f} completion tok/s (avg)")
    print(f"Avg model latency: {summary['avg_execution_time']:.2f}s per case")
    print(f"Total model time: {summary['total_execution_time']:.2f}s")
    if summary.get("peak_gpu_memory_mb") is not None:
        print(f"Peak GPU memory: {summary['peak_gpu_memory_mb']:.0f} MiB")
    print(f"Wall-clock run time: {summary['wall_time']:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every markdown benchmark case against a model and report the results."
    )
    parser.add_argument(
        "--config",
        default="llama-3.1-8B-instruct-q6",
        help="Model config name under configs/ to use (default: llama-3.1-8B-instruct-q6).",
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
    provider = ProviderFactory.create(config)
    prompt = PromptLoader.load("markdown_v1")

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    run_start = time.perf_counter()

    results: list[MarkdownCaseResult] = []
    for case_id in discover_cases():
        print(f"Running {case_id}...")
        try:
            result = run_case(case_id, provider, prompt, run_directory)
        except Exception as e:
            result = MarkdownCaseResult(
                case_id=case_id,
                difficulty=None,
                matched=False,
                execution_time=0.0,
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
