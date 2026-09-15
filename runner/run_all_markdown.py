"""
Run every markdown-extraction benchmark case under benchmark/markdown/
against a single model and report the results.

Usage:
    python -m runner.run_all_markdown --config llama-3.1-8B-instruct-q6
"""

import argparse
import json
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


@dataclass
class MarkdownCaseResult:
    case_id: str
    difficulty: int | None
    matched: bool
    execution_time: float
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

    case_directory = run_directory / case_id
    case_directory.mkdir(parents=True, exist_ok=True)
    (case_directory / "response.txt").write_text(response.content, encoding="utf-8")

    difficulty = case.metadata.get("difficulty")

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
    )


def print_report(results: list[MarkdownCaseResult]) -> None:
    total = len(results)
    matched_count = sum(1 for r in results if r.matched)

    print(f"\n{'Case':<10} {'Difficulty':<11} {'Matched':<9} {'Time (s)':<10} Error")
    for r in results:
        error_summary = (r.error or "").splitlines()[0] if r.error else ""
        print(
            f"{r.case_id:<10} {str(r.difficulty):<11} {str(r.matched):<9} "
            f"{r.execution_time:<10.2f} {error_summary}"
        )

    print(f"\nMatched: {matched_count}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every markdown benchmark case against a model and report the results."
    )
    parser.add_argument(
        "--config",
        default="llama-3.1-8B-instruct-q6",
        help="Model config name under configs/ to use (default: llama-3.1-8B-instruct-q6).",
    )
    args = parser.parse_args()

    config: ModelConfig = ConfigLoader.load(args.config)
    provider = ProviderFactory.create(config)
    prompt = PromptLoader.load("markdown_v1")

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

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

    print_report(results)

    report_path = run_directory / "report.json"
    report_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
